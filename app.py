# -*- coding: utf-8 -*-
"""
열화상 분기점검 보고서 자동 생성 웹앱 (Flask).

기능:
  - 사이트 선택 (조달청 청사 / 비축기지 / 티튜브)
  - 측정값 입력 (블록별 Point 1~3)
  - 사진 업로드 (블록별 실화상 + 열화상)
  - PDF 보고서 생성 + 다운로드

실행:
  python app.py
  → http://localhost:5000 접속
"""
import os
import re
import io
import json
import sqlite3
import hashlib
import math
from datetime import date, datetime, timedelta
from functools import wraps
from flask import (
    Flask, request, render_template, send_file,
    redirect, url_for, jsonify, flash, session, abort,
)
from werkzeug.utils import secure_filename
from report_engine import generate_report_pdf, SITE_PRESETS, B2_ITEMS, B6_ROW_LABELS
try:
    from flir_decode import decode_flir, get_temp_at_pixel, get_temp_in_box, extract_embedded_visible
    _FLIR_OK = True
except Exception as _flir_err:
    print(f"[WARN] flir_decode 로딩 실패: {_flir_err} — FLIR 자동분석 비활성화 (numpy 설치 필요)")
    decode_flir = get_temp_at_pixel = get_temp_in_box = None
    _FLIR_OK = False

# DATA_DIR: Render Persistent Disk 또는 로컬 폴더
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
REPORT_DIR = os.path.join(DATA_DIR, "reports")
DB_PATH    = os.path.join(DATA_DIR, "reports.db")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.jinja_env.auto_reload = True
app.secret_key = os.environ.get("SECRET_KEY", "thermal-report-dev-secret-CHANGE-ME")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "").strip()

# ============================================================
# SQLite DB — 저장된 보고서 관리 (draft + 정식 저장)
# ============================================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS saved_reports (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL,
        site_name   TEXT    NOT NULL,
        data_json   TEXT    NOT NULL,
        is_draft    INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT    NOT NULL,
        updated_at  TEXT    NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_saved_site ON saved_reports(site_name);
    CREATE INDEX IF NOT EXISTS idx_saved_draft ON saved_reports(is_draft);
    CREATE INDEX IF NOT EXISTS idx_saved_updated ON saved_reports(updated_at);

    CREATE TABLE IF NOT EXISTS saved_photos (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        sha         TEXT    NOT NULL UNIQUE,
        data_b64    TEXT    NOT NULL,
        mime        TEXT    NOT NULL,
        size_bytes  INTEGER NOT NULL,
        created_at  TEXT    NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_photo_sha ON saved_photos(sha);
    """)
    conn.commit()
    conn.close()

init_db()

# ============================================================
# 인증 — 비밀번호 단일 (APP_PASSWORD 환경변수)
#   - APP_PASSWORD 미설정 시 인증 우회 (로컬 개발)
# ============================================================
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if not APP_PASSWORD:
            return f(*args, **kwargs)
        if session.get("authed"):
            return f(*args, **kwargs)
        if request.path.startswith("/api/"):
            return jsonify({"error": "unauthorized"}), 401
        return redirect(url_for("login", next=request.path))
    return wrap

@app.route("/login", methods=["GET", "POST"])
def login():
    if not APP_PASSWORD:
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        pwd = request.form.get("password", "")
        if pwd == APP_PASSWORD:
            session["authed"] = True
            session.permanent = True
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)
        error = "비밀번호가 올바르지 않습니다."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    """메인 페이지 — 사이트 선택"""
    return render_template("index.html", sites=list(SITE_PRESETS.keys()))


@app.route("/site/<site_name>")
@login_required
def site_form(site_name):
    """선택한 사이트의 측정값/사진 입력 폼"""
    if site_name not in SITE_PRESETS:
        return redirect(url_for("index"))
    preset = SITE_PRESETS[site_name]
    return render_template("site_form.html",
                           site_name=site_name,
                           preset=preset,
                           b2_items=B2_ITEMS.get(site_name, []),
                           b6_labels=B6_ROW_LABELS,
                           today=date.today().isoformat())


# ============================================================
# v88 — 사진 슬롯 해석: request.files에 없으면 hidden form input(__photo__<slot>) → DB photo_id → 임시 파일 저장
# ============================================================
def _slot_to_temp_path(site_name: str, slot: str, payload: str) -> str | None:
    """payload는 JSON 문자열: {photo_id: N, name: "..."} 또는 {dataUrl: "...", name:"..."}
       성공 시 임시 파일 경로 반환, 실패 시 None."""
    import base64 as _b64, hashlib as _h
    try:
        obj = json.loads(payload) if isinstance(payload, str) else payload
        if not isinstance(obj, dict): return None
        data_url = None
        if obj.get("photo_id"):
            conn = get_db()
            row = conn.execute("SELECT mime, data_b64 FROM saved_photos WHERE id=?", (int(obj["photo_id"]),)).fetchone()
            conn.close()
            if not row:
                print(f"[WARN] photo_id={obj.get('photo_id')} DB에 없음 (slot={slot})")
                return None
            data_url = f"data:{row['mime']};base64,{row['data_b64']}"
        elif obj.get("dataUrl"):
            data_url = obj["dataUrl"]
        if not data_url or "," not in data_url:
            return None
        head, b64 = data_url.split(",", 1)
        # mime 추출
        mime = "image/jpeg"
        if head.startswith("data:") and ";" in head:
            mime = head[5:head.index(";")]
        ext = "jpg"
        if "png" in mime: ext = "png"
        elif "webp" in mime: ext = "webp"
        try:
            raw = _b64.b64decode(b64)
        except Exception:
            return None
        sha = _h.sha1(raw).hexdigest()[:12]
        fname = secure_filename(f"{site_name}_slot_{slot}_{sha}.{ext}")
        path = os.path.join(UPLOAD_DIR, fname)
        with open(path, "wb") as f:
            f.write(raw)
        return path
    except Exception as e:
        print(f"[WARN] _slot_to_temp_path 실패 slot={slot}: {e!r}")
        return None


@app.route("/generate", methods=["POST"])
@login_required
def generate():
    """폼 데이터로 PDF 생성 → 다운로드 (단계별 try/except)"""
    step = "초기화"
    try:
        step = "site_name 조회"
        site_name = request.form.get("site_name") or ""
        print(f"[INFO] /generate 시작: site_name={site_name!r}")
        if site_name not in SITE_PRESETS:
            return f"<h1>Unknown site: {site_name}</h1>", 400

        step = "preset 로드"
        preset = SITE_PRESETS[site_name]

        step = "blocks 수집"
        blocks = []
        for i, b in enumerate(preset["blocks"]):
            u_pts = []
            l_pts = []
            for j in range(3):
                v = (request.form.get(f"u{i}_p{j}", "") or "").strip()
                try: u_pts.append(float(v) if v else None)
                except: u_pts.append(None)
                v = (request.form.get(f"l{i}_p{j}", "") or "").strip()
                try: l_pts.append(float(v) if v else None)
                except: l_pts.append(None)
            blocks.append({
                "target": request.form.get(f"target{i}", b["target"]),
                "voltage": request.form.get(f"voltage{i}", b["voltage"]),
                "condition": request.form.get(f"condition{i}", b["condition"]),
                "upper_label": request.form.get(f"u_label{i}", b["upper_label"]),
                "upper_pts": u_pts,
                "lower_label": request.form.get(f"l_label{i}", b.get("lower_label", "")),
                "lower_pts": l_pts,
            })
        print(f"[INFO] blocks 수집 완료: {len(blocks)}개")

        step = "사진 저장"
        photos = {}
        # 슬롯명 → 실제 path 변환: 1차 multipart files, 2차 hidden __photo__<slot>
        def _resolve_slot(slot_name: str) -> str | None:
            # 1) request.files (즉시 업로드된 새 파일)
            f = request.files.get(slot_name)
            if f and f.filename:
                try:
                    fname = secure_filename(f"{site_name}_{slot_name}_{f.filename}")
                    p = os.path.join(UPLOAD_DIR, fname)
                    f.save(p)
                    return p
                except Exception as _fe:
                    print(f"[WARN] 사진 저장 실패 {slot_name}: {_fe!r}")
            # 2) hidden input __photo__<slot> (불러온 보고서, sessionStorage의 photo_id JSON)
            payload = request.form.get(f"__photo__{slot_name}")
            if payload:
                p = _slot_to_temp_path(site_name, slot_name, payload)
                if p:
                    print(f"[INFO] 사진 복원 (photo_id 경로): slot={slot_name}")
                    return p
            return None

        for i in range(len(blocks)):
            for kind in ["uv", "ut", "lv", "lt"]:
                field = f"photo_{i}_{kind}"
                p = _resolve_slot(field)
                if p:
                    photos.setdefault(i, {})[kind] = p
        print(f"[INFO] 사진 {sum(len(v) for v in photos.values())}장 (multipart + photo_id 합계)")

        step = "붙임8 처리"
        b8_pages = []
        for page_idx in range(len(preset.get("b8_captions", []))):
            items = []
            page_captions = preset["b8_captions"][page_idx]
            for slot in range(len(page_captions)):
                caption = (request.form.get(f"b8_{page_idx}_{slot}_caption", "") or "").strip()
                slot_name = f"b8_{page_idx}_{slot}_photo"
                p = _resolve_slot(slot_name)
                items.append((p, caption))
            b8_pages.append(items)

        step = "markers_json 파싱"
        markers_raw = {}
        try:
            raw_str = request.form.get("markers_json", "{}") or "{}"
            print(f"[INFO] markers_json 길이: {len(raw_str)}")
            if len(raw_str) > 2:
                print(f"[INFO] markers_json 처음 500자: {raw_str[:500]}")
            markers_raw = json.loads(raw_str)
            if not isinstance(markers_raw, dict):
                markers_raw = {}
            print(f"[INFO] markers 키: {list(markers_raw.keys())}")
            for k, v in markers_raw.items():
                sp = v.get('sp', {}) if isinstance(v, dict) else {}
                bx = v.get('bx', {}) if isinstance(v, dict) else {}
                sp_cnt = sum(1 for x in sp.values() if x)
                bx_cnt = sum(1 for x in bx.values() if x)
                print(f"[INFO]   {k}: SP={sp_cnt}개, BX={bx_cnt}개")
        except Exception as _je:
            print(f"[WARN] markers_json 파싱 실패: {_je!r}")
            markers_raw = {}

        step = "markers 통합"
        try:
            for key, info in markers_raw.items():
                m = re.match(r"^photo_(\d+)_(ut|lt)$", str(key))
                if not m: continue
                bi = int(m.group(1))
                kind = m.group(2)
                photos.setdefault(bi, {})[kind + "_markers"] = info
        except Exception as _me:
            print(f"[WARN] markers 통합 실패: {_me!r}")

        # 디버그: photos에 _markers 통합된 결과
        try:
            for bi, info in photos.items():
                if not isinstance(info, dict): continue
                mks = [k for k in info.keys() if k.endswith('_markers')]
                if mks:
                    print(f"[INFO] photos[{bi}] 키: {list(info.keys())}")
        except Exception as _de:
            print(f"[WARN] photos 디버그 실패: {_de!r}")
        
        step = "PDF 생성"
        year_month = (request.form.get("year_month", "") or "").strip()
        # v102 — 점검일 입력 시 표지/p2 연월 자동 동기화
        inspection_date = (request.form.get("inspection_date", "") or "").strip()
        if inspection_date and not year_month:
            m = re.match(r"(20\d{2})년\s*(\d{1,2})월", inspection_date)
            if m:
                year_month = f"{m.group(1)}.{m.group(2).zfill(2)}"
        # 주요 점검사항 / 점검결과 1~10
        p2_items = []
        p2_results = []
        for i in range(1, 11):
            iv = (request.form.get(f"p2_item_{i}", "") or "").strip()
            rv = (request.form.get(f"p2_result_{i}", "") or "").strip()
            p2_items.append(iv if iv else None)
            p2_results.append(rv if rv else None)
        if not any(p2_items): p2_items = None
        if not any(p2_results): p2_results = None
        # v115 — 페이지3 붙임 서류 목록 1~11
        p3_items = []
        for i in range(1, 12):
            iv = (request.form.get(f"p3_item_{i}", "") or "").strip()
            p3_items.append(iv if iv else None)
        if not any(p3_items): p3_items = None
        # v117 — 붙임2 항목별 점검결과/조치사항
        b2_results = {}
        b2_actions = {}
        for it in B2_ITEMS.get(site_name, []):
            rv = (request.form.get(f"b2_result_{it}", "") or "").strip()
            av = (request.form.get(f"b2_action_{it}", "") or "").strip()
            if rv: b2_results[it] = rv
            if av: b2_actions[it] = av
        # v118 — 붙임4 전압/전류/판정
        b4_voltages = {}
        for k in ("rs", "st", "tr"):
            v = (request.form.get(f"b4_v_{k}", "") or "").strip()
            if v: b4_voltages[k] = v
        b4_currents = {}
        for k in ("r", "s", "t"):
            v = (request.form.get(f"b4_a_{k}", "") or "").strip()
            if v: b4_currents[k] = v
        b4_results = {}
        for k in ("overheat", "ground", "pt_ct", "bolt", "control", "spd", "meter", "clean"):
            v = (request.form.get(f"b4_r_{k}", "") or "").strip()
            if v: b4_results[k] = v
        # v121 — 붙임6 점검결과 25행 + 종합의견
        b6_results = []
        for i in range(1, 26):
            v = (request.form.get(f"b6_r_{i}", "") or "").strip()
            b6_results.append(v if v else None)
        if not any(b6_results): b6_results = None
        b6_opinion = (request.form.get("b6_opinion", "") or "").strip() or None
        # 페이지별 포함 여부
        include_cover = bool(request.form.get("pdf_include_cover"))
        include_p2    = bool(request.form.get("pdf_include_p2"))
        include_p3    = bool(request.form.get("pdf_include_p3"))
        include_p4    = bool(request.form.get("pdf_include_p4"))
        # v112 — 붙임1~6 (1=p4와 동일, 4/5/6 신규)
        include_b1    = bool(request.form.get("pdf_include_b1"))
        include_b2    = bool(request.form.get("pdf_include_b2"))
        include_b3    = bool(request.form.get("pdf_include_b3"))
        include_b4    = bool(request.form.get("pdf_include_b4"))
        include_b5    = bool(request.form.get("pdf_include_b5"))
        include_b6    = bool(request.form.get("pdf_include_b6"))
        include_b7    = bool(request.form.get("pdf_include_b7"))
        include_b8    = bool(request.form.get("pdf_include_b8"))
        # 붙임3 입력값 수집
        b3_run = {}
        for k in ["dcv", "dca", "acv", "aca", "kw", "hz", "cum_mwh"]:
            v = (request.form.get(f"b3_{k}", "") or "").strip()
            if v: b3_run[k] = v
        b3_chk = {}
        for k in ["overheat", "ground", "voltage", "overcurrent", "fan", "spd", "filter", "clean"]:
            v = (request.form.get(f"b3_chk_{k}", "") or "").strip()
            if v: b3_chk[k] = v
        out_filename = f"보고서_{site_name.replace(' ', '_')}_{date.today().isoformat()}.pdf"
        out_path = os.path.join(REPORT_DIR, out_filename)
        print(f"[INFO] PDF 생성: ym={year_month!r}, cover={include_cover}, b3={include_b3}, b7={include_b7}, b8={include_b8}")
        generate_report_pdf(
            site_name=site_name,
            blocks=blocks if include_b7 else [],
            photos=photos,
            b8_pages=b8_pages if include_b8 else [],
            out_path=out_path,
            year_month=year_month,
            include_cover=include_cover,
            include_p2=include_p2,
            include_p3=include_p3,
            include_p4=include_p4,
            include_b1=include_b1,
            include_b2=include_b2,
            include_b3=include_b3,
            include_b4=include_b4,
            include_b5=include_b5,
            include_b6=include_b6,
            inspection_date=inspection_date,
            p2_items=p2_items,
            p2_results=p2_results,
            p3_items=p3_items,
            b2_results=b2_results,
            b2_actions=b2_actions,
            b4_voltages=b4_voltages,
            b4_currents=b4_currents,
            b4_results=b4_results,
            b6_results=b6_results,
            b6_opinion=b6_opinion,
            b3_run=b3_run,
            b3_chk=b3_chk,
        )
        print(f"[INFO] PDF 생성 성공!")

        step = "PDF 전송"
        return send_file(out_path, as_attachment=True, download_name=out_filename)
    except Exception as e:
        import traceback
        err_text = traceback.format_exc()
        print(f"[ERROR] /generate 단계={step} 실패:\n{err_text}")
        return (f"<h1>PDF 생성 실패</h1>"
                f"<p><b>실패 단계:</b> {step}</p>"
                f"<pre style='background:#fee;padding:10px;border:1px solid red;white-space:pre-wrap'>{err_text}</pre>"), 500


@app.route("/api/site_data/<site_name>")
@login_required
def api_site_data(site_name):
    """사이트 프리셋 JSON으로 반환 (Ajax 새로고침용)"""
    return jsonify(SITE_PRESETS.get(site_name, {}))




# ── FLIR 분석 캐시 ──────────────────────────────────────
_flir_cache = {}   # {md5_hash: decoded_result}


@app.route("/api/flir_decode", methods=["POST"])
@login_required
def api_flir_decode():
    """업로드된 R-JPEG에서 raw thermal + Planck 추출 → 메타데이터 반환."""
    if not _FLIR_OK:
        return jsonify({"is_flir": False, "error": "flir_decode unavailable"}), 200
    f = request.files.get("photo")
    if not f:
        return jsonify({"error": "no file"}), 400
    
    raw = f.read()
    h = hashlib.md5(raw).hexdigest()
    
    if h not in _flir_cache:
        tmp = os.path.join(UPLOAD_DIR, f"_flir_tmp_{h}.jpg")
        with open(tmp, "wb") as out:
            out.write(raw)
        result = decode_flir(tmp)
        visible_b64 = None
        try:
            vis_bytes = extract_embedded_visible(tmp)
            if vis_bytes:
                import base64
                visible_b64 = "data:image/jpeg;base64," + base64.b64encode(vis_bytes).decode("ascii")
        except Exception as _ve:
            print(f"[WARN] embedded visible 추출 실패: {_ve}")
        try: os.remove(tmp)
        except: pass
        if result is None:
            return jsonify({"error": "not a FLIR R-JPEG", "is_flir": False,
                            "visible_image_b64": visible_b64}), 200
        result["_visible_b64"] = visible_b64
        _flir_cache[h] = result

    r = _flir_cache[h]
    cal = {}
    for k, v in r["calibration"].items():
        if v is None: continue
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)): continue
        cal[k] = round(float(v), 6)

    return jsonify({
        "success": True,
        "is_flir": True,
        "hash": h,
        "width": r["width"],
        "height": r["height"],
        "temp_min": round(r["temp_min"], 1) if r["temp_min"] is not None else None,
        "temp_max": round(r["temp_max"], 1) if r["temp_max"] is not None else None,
        "temp_mean": round(r["temp_mean"], 1) if r["temp_mean"] is not None else None,
        "calibration": cal,
        "visible_image_b64": r.get("_visible_b64"),
    })


@app.route("/api/flir_temp", methods=["GET"])
@login_required
def api_flir_temp():
    """저장된 R-JPEG 분석 결과에서 좌표/박스의 온도 반환.
    Query: hash, sp1_x/sp1_y, sp2_x/sp2_y, sp3_x/sp3_y,
           bx1_x1/bx1_y1/bx1_x2/bx1_y2 (등)
    좌표는 raw thermal 이미지 (예: 160x120) 기준.
    """
    h = request.args.get("hash")
    if not h or h not in _flir_cache:
        return jsonify({"error": "not analyzed yet"}), 404
    
    decoded = _flir_cache[h]
    points = []
    for i in range(1, 4):
        sx = request.args.get(f"sp{i}_x")
        sy = request.args.get(f"sp{i}_y")
        if sx and sy:
            t = get_temp_at_pixel(decoded, int(sx), int(sy))
            points.append({"i": i, "x": int(sx), "y": int(sy), "temp": t})
    boxes = []
    for i in range(1, 4):
        x1 = request.args.get(f"bx{i}_x1")
        y1 = request.args.get(f"bx{i}_y1")
        x2 = request.args.get(f"bx{i}_x2")
        y2 = request.args.get(f"bx{i}_y2")
        if x1 and y1 and x2 and y2:
            b = get_temp_in_box(decoded, int(x1), int(y1), int(x2), int(y2))
            b.update({"i": i, "x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)})
            boxes.append(b)
    
    return jsonify({
        "success": True,
        "width": decoded["width"],
        "height": decoded["height"],
        "points": points,
        "boxes": boxes,
    })


# ============================================================
# 저장/불러오기 API
# ============================================================
@app.route("/api/save", methods=["POST"])
@login_required
def api_save():
    """폼 데이터를 JSON으로 저장. is_draft=0: 정식 저장, 1: 자동 백업."""
    payload = request.get_json(silent=True) or {}
    name      = (payload.get("name") or "").strip()
    site_name = (payload.get("site_name") or "").strip()
    data      = payload.get("data")
    is_draft  = 1 if payload.get("is_draft") else 0
    if not site_name or data is None:
        return jsonify({"error": "site_name과 data 필수"}), 400
    if not name:
        name = f"{site_name} {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    data_json = json.dumps(data, ensure_ascii=False)
    now = datetime.now().isoformat(timespec="seconds")

    conn = get_db()
    # draft는 site_name당 1개만 유지 (덮어쓰기)
    if is_draft:
        row = conn.execute("SELECT id FROM saved_reports WHERE site_name=? AND is_draft=1 ORDER BY id DESC LIMIT 1",
                           (site_name,)).fetchone()
        if row:
            conn.execute("UPDATE saved_reports SET name=?, data_json=?, updated_at=? WHERE id=?",
                         (name, data_json, now, row["id"]))
            new_id = row["id"]
        else:
            cur = conn.execute("INSERT INTO saved_reports(name,site_name,data_json,is_draft,created_at,updated_at) "
                               "VALUES (?,?,?,?,?,?)",
                               (name, site_name, data_json, 1, now, now))
            new_id = cur.lastrowid
    else:
        # 정식 저장 — 같은 name + site 있으면 덮어쓰기, 아니면 새로 INSERT
        row = conn.execute("SELECT id FROM saved_reports WHERE name=? AND site_name=? AND is_draft=0",
                           (name, site_name)).fetchone()
        if row:
            conn.execute("UPDATE saved_reports SET data_json=?, updated_at=? WHERE id=?",
                         (data_json, now, row["id"]))
            new_id = row["id"]
        else:
            cur = conn.execute("INSERT INTO saved_reports(name,site_name,data_json,is_draft,created_at,updated_at) "
                               "VALUES (?,?,?,?,?,?)",
                               (name, site_name, data_json, 0, now, now))
            new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"success": True, "id": new_id, "name": name, "is_draft": bool(is_draft)})

@app.route("/api/list")
@login_required
def api_list():
    """저장된 보고서 목록 반환. site_name 필터 가능."""
    site = request.args.get("site_name")
    conn = get_db()
    if site:
        rows = conn.execute("SELECT id,name,site_name,is_draft,created_at,updated_at "
                            "FROM saved_reports WHERE site_name=? ORDER BY updated_at DESC",
                            (site,)).fetchall()
    else:
        rows = conn.execute("SELECT id,name,site_name,is_draft,created_at,updated_at "
                            "FROM saved_reports ORDER BY updated_at DESC").fetchall()
    conn.close()
    return jsonify({"reports": [dict(r) for r in rows]})

@app.route("/api/load/<int:report_id>")
@login_required
def api_load(report_id):
    """특정 보고서 데이터 반환."""
    conn = get_db()
    row = conn.execute("SELECT * FROM saved_reports WHERE id=?", (report_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "id": row["id"],
        "name": row["name"],
        "site_name": row["site_name"],
        "is_draft": bool(row["is_draft"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "data": json.loads(row["data_json"]),
    })

@app.route("/api/delete/<int:report_id>", methods=["DELETE"])
@login_required
def api_delete(report_id):
    """저장된 보고서 삭제."""
    conn = get_db()
    conn.execute("DELETE FROM saved_reports WHERE id=?", (report_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# ============================================================
# 사진 업로드/조회 — 큰 dataURL을 클라이언트 sessionStorage가 아닌 서버 DB에 보관
# ============================================================
@app.route("/api/photo", methods=["POST"])
@login_required
def api_photo_upload():
    """클라이언트가 사진 dataURL을 POST → DB에 저장 → photo_id 반환.
    동일 sha면 기존 ID 재사용 (중복 저장 방지)."""
    import base64 as _b64, hashlib as _h
    payload = request.get_json(silent=True) or {}
    data_url = payload.get("dataUrl") or ""
    if not data_url or "," not in data_url:
        return jsonify({"error": "dataUrl 필요"}), 400
    head, b64 = data_url.split(",", 1)
    mime = "image/jpeg"
    if head.startswith("data:") and ";" in head:
        mime = head[5:head.index(";")]
    try:
        raw = _b64.b64decode(b64)
    except Exception:
        return jsonify({"error": "base64 디코드 실패"}), 400
    sha = _h.sha256(raw).hexdigest()
    size = len(raw)
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_db()
    row = conn.execute("SELECT id FROM saved_photos WHERE sha=?", (sha,)).fetchone()
    if row:
        conn.close()
        return jsonify({"id": row["id"], "size": size, "dedup": True})
    cur = conn.execute("INSERT INTO saved_photos(sha,data_b64,mime,size_bytes,created_at) VALUES(?,?,?,?,?)",
                       (sha, b64, mime, size, now))
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"id": pid, "size": size, "dedup": False})


@app.route("/api/photo/<int:photo_id>")
@login_required
def api_photo_get(photo_id):
    """photo_id → dataUrl 반환"""
    conn = get_db()
    row = conn.execute("SELECT mime, data_b64 FROM saved_photos WHERE id=?", (photo_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify({"dataUrl": "data:" + row["mime"] + ";base64," + row["data_b64"]})


@app.route("/api/draft/<site_name>")
@login_required
def api_draft(site_name):
    conn = get_db()
    row = conn.execute("SELECT * FROM saved_reports WHERE site_name=? AND is_draft=1 ORDER BY id DESC LIMIT 1", (site_name,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"draft": None})
    return jsonify({"draft": {"id": row["id"], "name": row["name"], "site_name": row["site_name"], "is_draft": True, "data_json": row["data_json"], "updated_at": row["updated_at"]}})


@app.route("/api/preview/<site>/<prefix>")
@login_required
def api_preview(site, prefix):
    return ("preview disabled", 410)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
