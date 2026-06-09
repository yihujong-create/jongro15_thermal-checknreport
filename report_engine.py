# -*- coding: utf-8 -*-
"""
보고서 PDF 생성 엔진 — 사내 양식(붙임7/붙임8) 1:1 매칭.
사이트 프리셋과 측정값/사진을 입력받아 PDF 파일을 생성한다.
"""
import os
import math
import random
from PIL import Image, ImageDraw, ImageFont

# ── 폰트 검색 (시스템에 설치된 한글 폰트 사용) ─────────────
_FONT_DIRS_KR = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "DroidSansFallback.ttf"),
    "/usr/share/fonts-droid-fallback/truetype/DroidSansFallback.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "C:/Windows/Fonts/malgun.ttf",   # Windows 맑은 고딕
    "C:/Windows/Fonts/NanumGothic.ttf",
]
_FONT_DIRS_LATIN = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "DejaVuSans.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
_FONT_DIRS_LATIN_B = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "DejaVuSans-Bold.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _find_font(candidates):
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


KR_FONT = _find_font(_FONT_DIRS_KR)
LATIN_R = _find_font(_FONT_DIRS_LATIN) or KR_FONT
LATIN_B = _find_font(_FONT_DIRS_LATIN_B) or KR_FONT or LATIN_R

# 페이지 크기
SCALE = 2.78
W, H = int(595 * SCALE), int(842 * SCALE)
PAGE_CX = 297.5


def is_kr(ch):
    cp = ord(ch)
    return (0xAC00 <= cp <= 0xD7A3) or (0x3130 <= cp <= 0x318F) or (0x4E00 <= cp <= 0x9FFF)


def _fp(bold, sz_pt):
    sz_px = int(sz_pt * SCALE)
    L = ImageFont.truetype(LATIN_B if bold else LATIN_R, sz_px)
    K = ImageFont.truetype(KR_FONT or LATIN_R, sz_px)
    return L, K


def tw(text, bold, sz):
    L, K = _fp(bold, sz)
    return sum((K if is_kr(ch) else L).getbbox(ch)[2] for ch in text)


def dtext(d, x, y, text, sz, bold=False, color="black", center=False):
    L, K = _fp(bold, sz)
    width = tw(text, bold, sz)
    px = x * SCALE - width / 2 if center else x * SCALE
    py = y * SCALE
    for ch in text:
        font = K if is_kr(ch) else L
        d.text((px, py), ch, fill=color, font=font)
        px += font.getbbox(ch)[2]


def rect(d, x, y, w, h, fill=None, outline="black", lw=1):
    x1, y1 = x * SCALE, y * SCALE
    x2, y2 = (x + w) * SCALE, (y + h) * SCALE
    if fill:
        d.rectangle([(x1, y1), (x2, y2)], fill=fill, outline=outline, width=lw)
    else:
        d.rectangle([(x1, y1), (x2, y2)], outline=outline, width=lw)


def _ccell(d, x, y, w, h, t, sz, bold=False, bg=None):
    rect(d, x, y, w, h, fill=(bg or "white"))
    L, K = _fp(bold, sz)
    w_text = tw(t, bold, sz)
    cx = (x + w / 2) * SCALE - w_text / 2
    cy = (y + h / 2) * SCALE - sz * SCALE * 0.55
    px = cx
    for ch in t:
        font = K if is_kr(ch) else L
        d.text((px, cy), ch, fill="black", font=font)
        px += font.getbbox(ch)[2]


def hcell(d, x, y, w, h, t, sz=10.6):
    _ccell(d, x, y, w, h, t, sz, bold=True, bg="#d9d9d9")


def dcell(d, x, y, w, h, t, sz=10.6):
    _ccell(d, x, y, w, h, t, sz)


def diag_cell(d, x, y, w, h, ur, ll, sz=10.6):
    rect(d, x, y, w, h, fill="#d9d9d9")
    d.line(
        [(x * SCALE, y * SCALE), ((x + w) * SCALE, (y + h) * SCALE)],
        fill="black", width=1,
    )
    L, K = _fp(False, sz)
    width = tw(ur, False, sz)
    px = (x + w) * SCALE - width - 10
    py = y * SCALE + 6
    for ch in ur:
        font = K if is_kr(ch) else L
        d.text((px, py), ch, fill="black", font=font)
        px += font.getbbox(ch)[2]
    width = tw(ll, False, sz)
    px = x * SCALE + 8
    py = (y + h) * SCALE - int(sz * SCALE) - 4
    for ch in ll:
        font = K if is_kr(ch) else L
        d.text((px, py), ch, fill="black", font=font)
        px += font.getbbox(ch)[2]


def _make_thermal_placeholder(sp_temps, max_t, min_t, seed=0):
    random.seed(seed)
    W_t, H_t = 800, 480
    im = Image.new("RGB", (W_t, H_t))
    px = im.load()
    hx = 0.4 + random.random() * 0.3
    hy = 0.3 + random.random() * 0.3
    for yy in range(H_t):
        for xx in range(W_t):
            hd_x = (xx - W_t * hx) / (W_t / 2)
            hd_y = (yy - H_t * hy) / (H_t / 2)
            dist = math.sqrt(hd_x * hd_x + hd_y * hd_y)
            t = max(0, 1 - min(dist, 1.0))
            if t < 0.2:
                tt = t / 0.2
                r = int(tt * 80); g = 0; b = int(tt * 120)
            elif t < 0.4:
                tt = (t - 0.2) / 0.2
                r = int(80 + tt * 175); g = 0; b = int(120 - tt * 90)
            elif t < 0.6:
                tt = (t - 0.4) / 0.2
                r = 255; g = int(tt * 80); b = int(30 + tt * 20)
            elif t < 0.8:
                tt = (t - 0.6) / 0.2
                r = 255; g = int(80 + tt * 130); b = int(50 + tt * 30)
            else:
                tt = (t - 0.8) / 0.2
                r = 255; g = int(210 + tt * 45); b = int(80 + tt * 175)
            px[xx, yy] = (r, g, b)
    return im


def _make_visible_placeholder(label_kr):
    im = Image.new("RGB", (800, 480), "#999")
    d = ImageDraw.Draw(im)
    d.rectangle([(0, 400), (800, 480)], fill="#5a5a5a")
    d.rectangle([(80, 60), (720, 400)], fill="#b0b0b0", outline="#333", width=3)
    d.line([(400, 60), (400, 400)], fill="#333", width=2)
    if KR_FONT:
        f = ImageFont.truetype(KR_FONT, 22)
        d.text((100, 410), label_kr[:30], fill="white", font=f)
    return im


def photo(img, path, x, y, w, h, placeholder_kind=None, placeholder_label=None,
          sp_temps=None, max_t=30, min_t=15, seed=0, markers=None):
    """사진 셀 — 외부 검정 테두리 + 흰 여백 + 사진 (또는 placeholder).
    markers: {sp: {1:{x,y,t}, 2:..., 3:...}, bx: {1:{x1,y1,x2,y2,...}, ...}, width, height}
    좌표는 raw thermal 픽셀 (예: 160x120) 기준."""
    BPX, PPX = 2, 4
    cell_w, cell_h = int(w * SCALE), int(h * SCALE)
    x0, y0 = int(x * SCALE), int(y * SCALE)
    d = ImageDraw.Draw(img)
    d.rectangle([(x0, y0), (x0 + cell_w, y0 + cell_h)], fill="white")
    iw = cell_w - 2 * (BPX + PPX)
    ih = cell_h - 2 * (BPX + PPX)
    ix = x0 + BPX + PPX
    iy = y0 + BPX + PPX
    if path and os.path.exists(path):
        try:
            p = Image.open(path).convert("RGB").resize((iw, ih))
            img.paste(p, (ix, iy))
        except Exception:
            d.rectangle([(ix, iy), (ix + iw, iy + ih)], fill="#e8e8e8")
    elif placeholder_kind == "thermal":
        p = _make_thermal_placeholder(sp_temps or [20, 20, 20],
                                       max_t, min_t, seed).resize((iw, ih))
        img.paste(p, (ix, iy))
    elif placeholder_kind == "visible":
        p = _make_visible_placeholder(placeholder_label or "사진").resize((iw, ih))
        img.paste(p, (ix, iy))
    else:
        d.rectangle([(ix, iy), (ix + iw, iy + ih)], fill="#e8e8e8")
    d.rectangle([(x0, y0), (x0 + cell_w, y0 + cell_h)],
                outline="black", width=BPX)
    
    # SP/BX 마커 그리기 — 최대 안전 모드 (단순 line/rectangle/text만 사용)
    if markers and isinstance(markers, dict):
        try:
            src_w = int(markers.get('width') or 160)
            src_h = int(markers.get('height') or 120)
            scale_x = float(iw) / max(1, src_w)
            scale_y = float(ih) / max(1, src_h)
            sp_dict = markers.get('sp') or {}
            bx_dict = markers.get('bx') or {}
            small_size = max(15, int(10 * SCALE * 0.6))   # 크기 확대
            # 글자별 폰트 선택을 위해 한글/영문 폰트 모두 로드
            try:
                fnt_kr = ImageFont.truetype(KR_FONT or LATIN_R, small_size)
            except Exception:
                fnt_kr = None
            try:
                fnt_lat = ImageFont.truetype(LATIN_R or KR_FONT, small_size)
            except Exception:
                fnt_lat = fnt_kr
            fnt = fnt_lat or fnt_kr  # 기본은 영문 폰트
            
            def _fnt_for(ch):
                """한글이면 KR, 그 외(영문/숫자/기호)는 LATIN"""
                cp = ord(ch)
                if 0xAC00 <= cp <= 0xD7A3 or 0x3040 <= cp <= 0x30FF or 0x4E00 <= cp <= 0x9FFF:
                    return fnt_kr or fnt_lat
                return fnt_lat or fnt_kr
            
            def safe_text_size(text):
                """글자별 폰트 너비 합산"""
                if fnt is None: return (len(text)*7, 12)
                try:
                    w = 0; h = 0
                    for ch in text:
                        f = _fnt_for(ch)
                        if f is None: continue
                        bb = f.getbbox(ch)
                        w += bb[2] - bb[0]
                        h = max(h, bb[3])
                    return (w, h)
                except Exception:
                    return (len(text) * small_size // 2, small_size)
            
            def _draw_text_mixed(nd, x, y, text, fill):
                """글자별 폰트로 한 줄 그리기"""
                for ch in text:
                    f = _fnt_for(ch)
                    if f is None: continue
                    try:
                        nd.text((x, y), ch, fill=fill, font=f)
                        bb = f.getbbox(ch)
                        x += bb[2] - bb[0]
                    except Exception:
                        pass
            
            def draw_label(text, lx, ly):
                """라벨 — Image.blend로 확실한 반투명 검정 배경 + 흰 글자"""
                try:
                    tw_, th_ = safe_text_size(text)
                    x1, y1, x2, y2 = lx-2, ly-1, lx+tw_+3, ly+th_+1
                    # 이미지 경계 클램프
                    iw_, ih_ = img.size
                    x1 = max(0, min(x1, iw_-1))
                    y1 = max(0, min(y1, ih_-1))
                    x2 = max(x1+1, min(x2, iw_))
                    y2 = max(y1+1, min(y2, ih_))
                    # 박스 영역 crop → 검정과 blend → 다시 paste
                    try:
                        region = img.crop((x1, y1, x2, y2)).convert('RGB')
                        tint = Image.new('RGB', region.size, (60, 60, 60))
                        blended = Image.blend(region, tint, 0.75)   # 75% 회색
                        img.paste(blended, (x1, y1))
                    except Exception:
                        ImageDraw.Draw(img).rectangle([(x1,y1),(x2,y2)], fill=(50,50,50))
                    nd = ImageDraw.Draw(img)
                    if fnt is not None:
                        _draw_text_mixed(nd, lx, ly, text, "white")
                    else:
                        nd.text((lx, ly), text, fill="white")
                except Exception:
                    pass
            
            # 1) SP 작은 +자 마커 + Sp 라벨
            try:
                for k_str, pt in sp_dict.items():
                    if not pt: continue
                    try:
                        px = ix + int(float(pt.get('x', 0)) * scale_x)
                        py = iy + int(float(pt.get('y', 0)) * scale_y)
                    except Exception:
                        continue
                    arm = int(9 * SCALE * 0.6)   # 마커 크기 확대
                    thick = max(3, int(2 * SCALE * 0.5))   # 두께 확대
                    try:
                        d.line([(px-arm-1, py), (px+arm+1, py)], fill="black", width=thick+2)
                        d.line([(px, py-arm-1), (px, py+arm+1)], fill="black", width=thick+2)
                        d.line([(px-arm, py), (px+arm, py)], fill="white", width=thick)
                        d.line([(px, py-arm), (px, py+arm)], fill="white", width=thick)
                    except Exception: pass
                    draw_label(f"Sp{k_str}", px + arm + 3, py - arm - 4)
            except Exception: pass
            
            # 2) BX 박스 + Bx 라벨
            try:
                for k_str, bx in bx_dict.items():
                    if not bx: continue
                    try:
                        bx1 = ix + int(float(bx.get('x1', 0)) * scale_x)
                        by1 = iy + int(float(bx.get('y1', 0)) * scale_y)
                        bx2 = ix + int(float(bx.get('x2', 0)) * scale_x)
                        by2 = iy + int(float(bx.get('y2', 0)) * scale_y)
                    except Exception:
                        continue
                    thick = max(2, int(1 * SCALE * 0.5))
                    try:
                        d.rectangle([(bx1-1, by1-1), (bx2+1, by2+1)], outline="black", width=1)
                        d.rectangle([(bx1, by1), (bx2, by2)], outline="white", width=thick)
                    except Exception: pass
                    ly = by1 - int(7 * SCALE * 0.5)
                    if ly < iy: ly = by1 + 2
                    draw_label(f"Bx{k_str}", bx1, ly)
                    # 핫스팟 ▲ (빨강, max 위치) / 콜드스팟 ▼ (파랑, min 위치)
                    try:
                        tri_h = int(7 * SCALE * 0.5)
                        tri_w = int(4 * SCALE * 0.5)
                        if bx.get('max_x') is not None and bx.get('max_y') is not None:
                            hx = ix + int(float(bx['max_x']) * scale_x)
                            hy = iy + int(float(bx['max_y']) * scale_y)
                            outer = [(hx, hy-tri_h-1), (hx-tri_w-1, hy+tri_h//2+1), (hx+tri_w+1, hy+tri_h//2+1)]
                            inner = [(hx, hy-tri_h), (hx-tri_w, hy+tri_h//2), (hx+tri_w, hy+tri_h//2)]
                            d.polygon(outer, fill="black")
                            d.polygon(inner, fill=(255, 48, 48))
                        if bx.get('min_x') is not None and bx.get('min_y') is not None:
                            cx2 = ix + int(float(bx['min_x']) * scale_x)
                            cy2 = iy + int(float(bx['min_y']) * scale_y)
                            outer = [(cx2, cy2+tri_h+1), (cx2-tri_w-1, cy2-tri_h//2-1), (cx2+tri_w+1, cy2-tri_h//2-1)]
                            inner = [(cx2, cy2+tri_h), (cx2-tri_w, cy2-tri_h//2), (cx2+tri_w, cy2-tri_h//2)]
                            d.polygon(outer, fill="black")
                            d.polygon(inner, fill=(32, 128, 255))
                    except Exception: pass
            except Exception: pass
            
            # 3) 좌측 상단 정보 박스 (SP/BX 온도 리스트)
            try:
                lines = []
                for k_str in ['1','2','3']:
                    p = sp_dict.get(k_str) if isinstance(sp_dict, dict) else None
                    if p is None and isinstance(sp_dict, dict):
                        p = sp_dict.get(int(k_str)) if k_str.isdigit() else None
                    if not p: continue
                    t = p.get('t')
                    if t is None: continue
                    try: lines.append(f"Sp{k_str}   {float(t):.1f} °C")
                    except Exception: pass
                for k_str in ['1','2','3']:
                    b = bx_dict.get(k_str) if isinstance(bx_dict, dict) else None
                    if b is None and isinstance(bx_dict, dict):
                        b = bx_dict.get(int(k_str)) if k_str.isdigit() else None
                    if not b: continue
                    mx, mn, av = b.get('max'), b.get('min'), b.get('avg')
                    try:
                        if mx is not None: lines.append(f"Bx{k_str} max   {mx} °C")
                        if mn is not None: lines.append(f"Bx{k_str} min   {mn} °C")
                        if av is not None: lines.append(f"Bx{k_str} avg   {av} °C")
                    except Exception: pass
                
                if lines and fnt is not None:
                    pad_x = max(4, int(4 * SCALE * 0.5))
                    pad_y = max(3, int(3 * SCALE * 0.5))
                    gap = max(2, int(2 * SCALE * 0.5))
                    sizes = [safe_text_size(t) for t in lines]
                    total_w = max(s[0] for s in sizes) + pad_x*2
                    total_h = sum(s[1] for s in sizes) + gap*(len(sizes)-1) + pad_y*2
                    ox = ix + max(3, int(3 * SCALE * 0.5))
                    oy = iy + max(3, int(3 * SCALE * 0.5))
                    # 반투명 회색 박스 + 흰 외곽선 (어두운 사진 위에서도 구별)
                    try:
                        bx1, by1, bx2, by2 = ox, oy, ox+total_w, oy+total_h
                        IW_, IH_ = img.size
                        bx1 = max(0, min(bx1, IW_-1))
                        by1 = max(0, min(by1, IH_-1))
                        bx2 = max(bx1+1, min(bx2, IW_))
                        by2 = max(by1+1, min(by2, IH_))
                        region = img.crop((bx1, by1, bx2, by2)).convert('RGB')
                        tint = Image.new('RGB', region.size, (95, 95, 95))
                        blended = Image.blend(region, tint, 0.70)   # 70% 회색 + 30% 사진
                        img.paste(blended, (bx1, by1))
                        d = ImageDraw.Draw(img)
                        d.rectangle([(bx1, by1), (bx2-1, by2-1)], outline=(255,255,255), width=1)
                    except Exception:
                        d.rectangle([(ox, oy), (ox+total_w, oy+total_h)], fill=(60,60,60), outline="white", width=1)
                    cy = oy + pad_y
                    for text, (tw_, th_) in zip(lines, sizes):
                        try:
                            _draw_text_mixed(d, ox+pad_x, cy, text, "white")
                        except Exception: pass
                        cy += th_ + gap
            except Exception: pass
        except Exception as _e:
            try: print(f"[WARN] photo() markers 처리 실패: {_e!r}")
            except: pass


def calc_diff(pts):
    valid = [p for p in pts if p is not None]
    if len(valid) < 2:
        return None
    return round(max(valid) - min(valid), 1)


def fmt_pt(v):
    return f"{v}" if v is not None else "-"


def fmt_diff(d):
    return f"{d}" if d is not None else "-"


def verdict_text(max_diff, tn=5, tw=10):
    if max_diff is None or max_diff <= tn:
        return "   부위별 온도차 5°C 이하 : 정상"
    elif max_diff <= tw:
        return "   부위별 온도차 5°C 초과 ~ 10°C : 요주의"
    else:
        return "   부위별 온도차 10°C 이상 : 이상"


def render_b7(block, page_num, photos=None, seed=0):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    # 디버그: photos에 마커 포함되어 있는지
    try:
        if photos:
            for k, v in (photos or {}).items():
                if isinstance(v, str): continue
                if isinstance(v, dict) and any(kk.endswith('_markers') for kk in v.keys()):
                    print(f"[INFO] render_b7 page={page_num} target={block.get('target')!r} photos keys={list(v.keys())}")
                    for mk in ['ut_markers', 'lt_markers']:
                        if mk in v:
                            mi = v[mk] or {}
                            sp_n = sum(1 for x in (mi.get('sp') or {}).values() if x)
                            bx_n = sum(1 for x in (mi.get('bx') or {}).values() if x)
                            print(f"[INFO]   {mk}: width={mi.get('width')}, height={mi.get('height')}, SP={sp_n}, BX={bx_n}")
    except Exception as _e:
        print(f"[WARN] render_b7 디버그 실패: {_e!r}")
    
    dtext(d, 86, 56, "<붙임7>", 11.5, bold=True)
    dtext(d, PAGE_CX, 52, "적외선 열화상분포 측정기록표", 14.4, bold=True, center=True)
    bw = (552 - 43) / 6
    for i, (lbl, val) in enumerate([
        ("측정대상", block["target"]),
        ("사용전압", block["voltage"]),
        ("측정조건", block["condition"]),
    ]):
        hcell(d, 43 + i * 2 * bw, 85, bw, 22, lbl)
        dcell(d, 43 + (i * 2 + 1) * bw, 85, bw, 22, str(val))
    dtext(d, 43, 134, " 1. 판정기준(3상 비교법)", 10.6, bold=True)
    wH, wJ, wY, wI, wB = 152, 90, 110, 90, 67
    xs = [43]
    for w in [wH, wJ, wY, wI]:
        xs.append(xs[-1] + w)
    diag_cell(d, xs[0], 152, wH, 22, "구 분", "판정요소")
    hcell(d, xs[1], 152, wJ, 22, "정상")
    hcell(d, xs[2], 152, wY, 22, "요주의")
    hcell(d, xs[3], 152, wI, 22, "이 상")
    hcell(d, xs[4], 152, wB, 22, "비 고")
    dcell(d, xs[0], 174, wH, 22, "온도차")
    dcell(d, xs[1], 174, wJ, 22, "5°C 이하")
    dcell(d, xs[2], 174, wY, 22, "5°C 초과 ~ 10°C")
    dcell(d, xs[3], 174, wI, 22, "10°C 이상")
    dcell(d, xs[4], 174, wB, 22, "")
    dtext(d, 43, 210, "* 온도차는 최고치와 최저치의 차이임.", 10.6)
    dtext(d, 43, 249, " 2. 부위별 측정온도", 10.6, bold=True)
    cw2 = [165, 88, 88, 88, 86]
    xs2 = [43]
    for w in cw2[:-1]:
        xs2.append(xs2[-1] + w)
    for i, h in enumerate(["측정부위", "Point 1", "Point 2", "Point 3", "온도차"]):
        hcell(d, xs2[i], 267, cw2[i], 20, h)
    u_diff = calc_diff(block["upper_pts"])
    dcell(d, xs2[0], 287, cw2[0], 20, str(block["upper_label"] or "-"))
    for i, p in enumerate(block["upper_pts"]):
        dcell(d, xs2[i + 1], 287, cw2[i + 1], 20, fmt_pt(p))
    dcell(d, xs2[4], 287, cw2[4], 20, fmt_diff(u_diff))
    has_lower = block.get("lower_label") and any(
        p is not None for p in block.get("lower_pts", [])
    )
    l_diff = None
    if has_lower:
        l_diff = calc_diff(block["lower_pts"])
        dcell(d, xs2[0], 307, cw2[0], 20, str(block["lower_label"] or "-"))
        for i, p in enumerate(block["lower_pts"]):
            dcell(d, xs2[i + 1], 307, cw2[i + 1], 20, fmt_pt(p))
        dcell(d, xs2[4], 307, cw2[4], 20, fmt_diff(l_diff))
    dtext(d, 43, 346, " 3. 측정부위의 Thermographic", 10.6, bold=True)

    photos = photos or {}
    u_pts = block["upper_pts"]
    u_max = round(max([p for p in u_pts if p is not None] or [25]) + 1, 1)
    u_min = round(min([p for p in u_pts if p is not None] or [15]) - 5, 1)

    if has_lower:
        l_pts = block["lower_pts"]
        l_max = round(max([p for p in l_pts if p is not None] or [25]) + 1, 1)
        l_min = round(min([p for p in l_pts if p is not None] or [15]) - 5, 1)
        photo(img, photos.get("uv"), 45.4, 371.3, 246.7, 149.4,
              placeholder_kind="visible", placeholder_label=block["upper_label"])
        photo(img, photos.get("ut"), 301.7, 371.3, 246.7, 149.4,
              placeholder_kind="thermal", sp_temps=u_pts,
              max_t=u_max, min_t=u_min, seed=seed,
              markers=photos.get("ut_markers"))
        photo(img, photos.get("lv"), 45.4, 526.8, 246.7, 149.4,
              placeholder_kind="visible", placeholder_label=block["lower_label"])
        photo(img, photos.get("lt"), 301.7, 526.8, 246.7, 149.4,
              placeholder_kind="thermal", sp_temps=l_pts,
              max_t=l_max, min_t=l_min, seed=seed + 1,
              markers=photos.get("lt_markers"))
    else:
        # 사진 2장 (세로 중앙 배치)
        photo(img, photos.get("uv"), 45.4, 449.05, 246.7, 149.4,
              placeholder_kind="visible", placeholder_label=block["upper_label"])
        photo(img, photos.get("ut"), 301.7, 449.05, 246.7, 149.4,
              placeholder_kind="thermal", sp_temps=u_pts,
              max_t=u_max, min_t=u_min, seed=seed,
              markers=photos.get("ut_markers"))

    diffs = [d for d in [u_diff, l_diff] if d is not None]
    max_d = max(diffs) if diffs else None
    dtext(d, 43, 698, " 4. 종합의견", 10.6, bold=True)
    rect(d, 43, 716, 509, 24, fill="white")
    dtext(d, 50, 720, verdict_text(max_d), 10.6)
    dtext(d, PAGE_CX, 793, f"-  {page_num}  -", 10.6, center=True)
    return img


def render_b8(items, page_num):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    dtext(d, 43, 64, "<붙임8>", 10.6)
    dtext(d, PAGE_CX, 62, "점검사진대지", 14.4, bold=True, center=True)
    positions = [(45.4, 157.4), (301.7, 157.4), (45.4, 468.5), (301.7, 468.5)]
    caps = [(131, 360), (377, 360), (131, 671), (377, 671)]
    for i in range(4):
        path, caption = items[i] if i < len(items) else (None, "")
        x, y = positions[i]
        photo(img, path, x, y, 246.7, 188.3,
              placeholder_kind="visible", placeholder_label=caption)
        cx, cy = caps[i]
        dtext(d, cx, cy, caption, 10.6)
    dtext(d, PAGE_CX, 793, f"-  {page_num}  -", 10.6, center=True)
    return img


# ── 사이트 프리셋 (Excel 시트에서 추출한 측정 블록) ─────────

# ============================================================
# 표지 (p1) 합성 — PDF 템플릿 PNG에 연월만 동적 그리기
# ============================================================
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PDF_TPL_DIR = os.path.join(_BASE_DIR, "templates_pdf")

# v109 — 사이트 한글명 → 영문 키 매핑 (Git/Render 파일명 인코딩 회피)
SITE_KEY_MAP = {
    "조달청 청사": "jodalcheong",
    "비축기지":   "bichuk",
    "티튜브":     "titube",
}

def _site_key(site_name: str) -> str:
    """사이트명을 파일명 안전한 키로 변환. 없으면 원본 반환(폴백)."""
    return SITE_KEY_MAP.get(site_name, site_name)


def _template_pdf_path(prefix: str, site_name: str) -> str:
    """templates_pdf/<prefix>_<key>.pdf 경로 반환. 영문 키 우선, 한글 폴백."""
    eng = os.path.join(_PDF_TPL_DIR, f"{prefix}_{_site_key(site_name)}.pdf")
    if os.path.exists(eng):
        return eng
    return os.path.join(_PDF_TPL_DIR, f"{prefix}_{site_name}.pdf")

# 사이트별 표지 연월 좌표 매핑 (300DPI 기준)
COVER_YM_BOX = {
    "조달청 청사": (1100, 2065, 1380, 2135),
    "비축기지":   (1110, 1895, 1370, 1960),
    "티튜브":     (1110, 1870, 1370, 1935),
}

def _normalize_ym(year_month: str) -> str:
    """'2026.06'/'2026-06'/'2026/6' → '2026. 06'."""
    s = (year_month or "").strip().replace("-", ".").replace("/", ".")
    parts = [p.strip() for p in s.split(".") if p.strip()]
    if len(parts) >= 2:
        return f"{parts[0]}. {parts[1].zfill(2)}"
    return s


def _pil_kr(size_px: int):
    """DroidSansFallback ImageFont (한글)."""
    p = os.path.join(_BASE_DIR, "fonts", "DroidSansFallback.ttf")
    if os.path.exists(p):
        try: return ImageFont.truetype(p, size_px)
        except Exception: pass
    if KR_FONT:
        try: return ImageFont.truetype(KR_FONT, size_px)
        except Exception: pass
    return ImageFont.load_default()


def _pil_ascii(size_px: int):
    """DejaVuSans ImageFont (ASCII/숫자)."""
    p = os.path.join(_BASE_DIR, "fonts", "DejaVuSans.ttf")
    if os.path.exists(p):
        try: return ImageFont.truetype(p, size_px)
        except Exception: pass
    if LATIN_R:
        try: return ImageFont.truetype(LATIN_R, size_px)
        except Exception: pass
    return _pil_kr(size_px)


def _draw_mixed(d, x, y, text, size_px, fill="black"):
    """글자별로 한글/ASCII 폰트 선택해서 그리기."""
    kr = _pil_kr(size_px)
    asc = _pil_ascii(size_px)
    cur_x = x
    for ch in text:
        cp = ord(ch)
        if (0xAC00 <= cp <= 0xD7A3) or (0x3130 <= cp <= 0x318F) or (0x3000 <= cp <= 0x303F):
            f = kr
        else:
            f = asc
        d.text((cur_x, y), ch, font=f, fill=fill)
        bb = f.getbbox(ch)
        cur_x += bb[2] - bb[0]
    return cur_x


def _render_pdf_page_to_img(pdf_path: str):
    """PDF 파일의 첫 페이지를 1654x2339 PIL Image로 렌더링 (200 DPI A4).
    v114 — 메모리 절감을 위해 처음부터 낮은 해상도로 렌더링 (이전 25MB → 11MB).
    """
    import fitz
    doc = fitz.open(pdf_path)
    page = doc[0]
    # A4 200 DPI = 1654 x 2339 (이전 2481x3509 → 56% 메모리)
    scale_x = 1654 / page.rect.width
    scale_y = 2339 / page.rect.height
    pix = page.get_pixmap(matrix=fitz.Matrix(scale_x, scale_y))
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGB")
    if img.size != (1654, 2339):
        img = img.resize((1654, 2339), Image.LANCZOS)
    return img, page, doc, scale_x, scale_y


def render_cover(site_name: str, year_month: str = "") -> "Image.Image":
    """표지: 원본 PDF를 이미지로 + 연월 영역만 PIL로 덮어쓰기.

    year_month: "2026.06" 등. 빈 문자열이면 원본 그대로.
    """
    pdf_path = _template_pdf_path("cover", site_name)
    if os.path.exists(pdf_path):
        try:
            img, page, doc, sx, sy = _render_pdf_page_to_img(pdf_path)
            if year_month:
                new_ym = _normalize_ym(year_month)
                # 원본 PDF에서 "20YY. MM" 패턴 찾기
                import re as _re
                for block in page.get_text("dict")["blocks"]:
                    if "lines" not in block: continue
                    for line in block["lines"]:
                        for span in line["spans"]:
                            t = span["text"].strip()
                            if _re.fullmatch(r"20\d{2}\.\s*\d{1,2}", t):
                                bb = span["bbox"]
                                size_pt = span["size"]
                                d = ImageDraw.Draw(img)
                                pad = 3
                                d.rectangle([bb[0]*sx - pad, bb[1]*sy - pad,
                                             bb[2]*sx + pad, bb[3]*sy + pad], fill="white")
                                size_px = int(size_pt * sy * 0.95)
                                _draw_mixed(d, bb[0]*sx, bb[1]*sy - 1, new_ym, size_px)
            doc.close()
            return img
        except Exception as _e:
            print(f"[WARN] render_cover PDF 실패: {_e!r}, PNG 폴백")
    # 폴백 — PNG 사용
    fn = os.path.join(_PDF_TPL_DIR, f"cover_{site_name}.png")
    if not os.path.exists(fn):
        return Image.new("RGB", (2481, 3509), "white")
    img = Image.open(fn).convert("RGB")
    if not year_month:
        return img
    box = COVER_YM_BOX.get(site_name, (1100, 2065, 1380, 2135))
    x1, y1, x2, y2 = box
    d = ImageDraw.Draw(img)
    d.rectangle([x1, y1, x2, y2], fill="white")
    s = _normalize_ym(year_month)
    size_px = 52
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2 - size_px // 2
    _draw_mixed(d, cx - len(s)*size_px//4, cy, s, size_px)
    return img


# ============================================================
# v102 — 페이지 2/3/4: 원본 PDF 그대로 + 페이지 2의 편집 필드만 PIL로 덮어쓰기
# ============================================================
DEFAULT_P2_ITEMS = [
    "1. 특고압 전기설비 외관 점검",
    "2. 적외선 열화상 진단",
    "3. 모듈 외관 점검",
    "4. 전압, 전류, 발전량 등 측정",
    "5. 인버터 판넬 점검",
    "6. 접속반 점검",
]
DEFAULT_P2_RESULTS = [
    "1-1. 외관 이상없음",
    "2-1. 적외선 열화상진단결과 중점적으로 단자체크 조임부분 이상 없음",
    "3-1. 모듈외관이 손상되거나 오염된 부분은 없음",
    "4-1. 전압 전류, 발전량 측정결과 현장 이상 없음",
    "5-1. 인버터 판넬 이상 없음",
    "6-1. 접속반 이상 없음",
]


def render_p2(site_name: str, year_month: str = "", inspection_date: str = "",
              items: list = None, results: list = None) -> "Image.Image":
    """페이지 2 — 점검일/주요점검사항/점검결과/연월만 동적 교체."""
    pdf_path = _template_pdf_path("p2", site_name)
    if not os.path.exists(pdf_path):
        return Image.new("RGB", (2481, 3509), "white")
    img, page, doc, sx, sy = _render_pdf_page_to_img(pdf_path)
    d = ImageDraw.Draw(img)

    # 교체 매핑
    replacements = {}
    if inspection_date:
        import re as _re
        for block in page.get_text("dict")["blocks"]:
            if "lines" not in block: continue
            for line in block["lines"]:
                for span in line["spans"]:
                    t = span["text"].strip()
                    if _re.fullmatch(r"20\d{2}년\s*\d{1,2}월\s*\d{1,2}일", t):
                        replacements[t] = inspection_date
    if year_month:
        new_ym = _normalize_ym(year_month)
        import re as _re
        for block in page.get_text("dict")["blocks"]:
            if "lines" not in block: continue
            for line in block["lines"]:
                for span in line["spans"]:
                    t = span["text"].strip()
                    if _re.fullmatch(r"20\d{2}\.\s*\d{1,2}", t):
                        replacements[t] = new_ym
    use_items = list(items) if items else [None] * 10
    while len(use_items) < 10: use_items.append(None)
    use_results = list(results) if results else [None] * 10
    while len(use_results) < 10: use_results.append(None)
    for i, orig in enumerate(DEFAULT_P2_ITEMS):
        new = use_items[i]
        if new and new.strip() and new != orig:
            replacements[orig] = new
    for i, orig in enumerate(DEFAULT_P2_RESULTS):
        new = use_results[i]
        if new and new.strip() and new != orig:
            replacements[orig] = new

    # 1) PDF spans을 순회하면서 redact + PIL로 교체 텍스트 그리기
    for block in page.get_text("dict")["blocks"]:
        if "lines" not in block: continue
        for line in block["lines"]:
            for span in line["spans"]:
                orig = span["text"]
                new_text = replacements.get(orig) or replacements.get(orig.strip())
                if not new_text or new_text == orig.strip(): continue
                bb = span["bbox"]
                size_pt = span["size"]
                pad = 2
                d.rectangle([bb[0]*sx - pad, bb[1]*sy - pad,
                             bb[2]*sx + pad, bb[3]*sy + pad], fill="white")
                size_px = int(size_pt * sy * 0.95)
                _draw_mixed(d, bb[0]*sx, bb[1]*sy - 1, new_text, size_px)

    # 2) 추가 항목 7~10 (items) / 결과 7-1~10-1 (results)
    items_x_pdf = 192.5
    items_y_start = 272.6
    items_dy = 12.9
    items_size_pt = 10.6
    results_y_start = 447.5
    size_px_extra = int(items_size_pt * sy * 0.95)
    for i in range(6, 10):
        txt = use_items[i]
        if txt and txt.strip():
            x = items_x_pdf * sx
            y = (items_y_start + i * items_dy) * sy
            _draw_mixed(d, x, y, txt, size_px_extra)
    for i in range(6, 10):
        txt = use_results[i]
        if txt and txt.strip():
            x = items_x_pdf * sx
            y = (results_y_start + i * items_dy) * sy
            _draw_mixed(d, x, y, txt, size_px_extra)

    doc.close()
    return img


# v115 — 페이지 3 (붙임 서류 목록) 사이트별 기본값
DEFAULT_P3_ITEMS = {
    "조달청 청사": [
        "1. 안전진단장비 1부",
        "2. 송 수전설비 점검기록표 1부",
        "3. 인버터 점검기록표 1부",
        "4. ACB PANEL 점검기록표 1부",
        "5. 접속반 및 모듈 점검기록표 1부",
        "6. 태양광발전설비 점검기록표 1부",
        "7. 열화상분포 측정기록표 1부",
        "8. 점검사진대지 1부",
    ],
    "비축기지": [
        "1. 안전진단장비 1부",
        "2. 송 수전설비 점검기록표 1부",
        "3. 인버터 점검기록표 1부",
        "4. ACB PANEL 점검기록표 1부",
        "5. 접속반 및 모듈 점검기록표 1부",
        "6. 태양광발전설비 점검기록표 1부",
        "7. 열화상분포 측정기록표 1부",
        "8. 점검사진대지 1부",
        "9. 전기설비 절연저항 측정기록표 1부",
        "10. 전기설비 접지저항 측정기록표 1부",
        "11. 변압기 점검기록표 1부",
    ],
    "티튜브": [
        "1. 안전진단장비 1부",
        "2. 송 수전설비 점검기록표 1부",
        "3. 인버터 점검기록표 1부",
        "4. ACB PANEL 점검기록표 1부",
        "5. 접속반 및 모듈 점검기록표 1부",
        "6. 태양광발전설비 점검기록표 1부",
        "7. 열화상분포 측정기록표 1부",
        "8. 점검사진대지 1부",
        "9. 전기설비 절연저항 측정기록표 1부",
        "10. 전기설비 접지저항 측정기록표 1부",
        "11. 변압기 점검기록표 1부",
    ],
}


def render_p3(site_name: str, items: list = None) -> "Image.Image":
    """페이지 3 — 붙임 서류 목록. items로 항목 텍스트 교체 가능."""
    pdf_path = _template_pdf_path("p3", site_name)
    if not os.path.exists(pdf_path):
        return Image.new("RGB", (2481, 3509), "white")
    img, page, doc, sx, sy = _render_pdf_page_to_img(pdf_path)
    # items가 있으면 PDF span을 찾아서 새 텍스트로 교체
    try:
        defaults = DEFAULT_P3_ITEMS.get(site_name, [])
        if items and defaults:
            d = ImageDraw.Draw(img)
            replacements = {}
            for i, orig in enumerate(defaults):
                if i < len(items):
                    new = items[i]
                    if new and new.strip() and new.strip() != orig:
                        replacements[orig] = new.strip()
            if replacements:
                for block in page.get_text("dict")["blocks"]:
                    if "lines" not in block: continue
                    for line in block["lines"]:
                        for span in line["spans"]:
                            orig = span["text"]
                            new_text = (replacements.get(orig) or
                                        replacements.get(orig.strip()))
                            if not new_text or new_text == orig.strip():
                                continue
                            bb = span["bbox"]
                            size_pt = span["size"]
                            pad = 2
                            d.rectangle([bb[0]*sx - pad, bb[1]*sy - pad,
                                         bb[2]*sx + pad, bb[3]*sy + pad],
                                        fill="white")
                            size_px = int(size_pt * sy * 0.95)
                            _draw_mixed(d, bb[0]*sx, bb[1]*sy - 1,
                                        new_text, size_px)
    except Exception as _e:
        print(f"[WARN] render_p3 항목 교체 실패: {_e!r}")
    doc.close()
    return img


def render_p4(site_name: str) -> "Image.Image":
    """페이지 4 (붙임1) — 원본 그대로."""
    pdf_path = _template_pdf_path("p4", site_name)
    if not os.path.exists(pdf_path):
        return Image.new("RGB", (2481, 3509), "white")
    img, _, doc, _, _ = _render_pdf_page_to_img(pdf_path)
    doc.close()
    return img


# v112 — 정적 페이지 렌더 함수 (붙임1~6, 9, 10) — 원본 PDF 그대로
def render_static_page(site_name: str, prefix: str) -> "Image.Image":
    """templates_pdf/<prefix>_<site>.pdf를 그대로 이미지로 반환."""
    pdf_path = _template_pdf_path(prefix, site_name)
    if not os.path.exists(pdf_path):
        return Image.new("RGB", (2481, 3509), "white")
    img, _, doc, _, _ = _render_pdf_page_to_img(pdf_path)
    doc.close()
    return img


def render_b1(site_name): return render_static_page(site_name, "b1")


B9_DATA = {
    "비축기지": [
        {"target":"[MJB-1]", "desc":"DC1000V FUSE15A / 1CH~20CH", "v":"DC 799", "std":"1 이상", "meas":"4", "result":"양호", "note":""},
        {"target":"[MJB-2]", "desc":"DC1000V FUSE15A / 1CH~20CH", "v":"DC 797", "std":"1 이상", "meas":"3", "result":"양호", "note":""},
        {"target":"[MJB-3]", "desc":"DC1000V FUSE15A / 1CH~20CH", "v":"DC 792", "std":"1 이상", "meas":"4", "result":"양호", "note":""},
        {"target":"[MJB-4]", "desc":"DC1000V FUSE15A / 1CH~20CH", "v":"DC 792", "std":"1 이상", "meas":"3", "result":"양호", "note":""},
        {"target":"[MJB-5]", "desc":"DC1000V FUSE15A / 1CH~11CH", "v":"DC 795", "std":"1 이상", "meas":"3", "result":"양호", "note":""},
        {"target":"[MJB-6]", "desc":"DC1000V FUSE15A / 1CH~12CH", "v":"DC 791", "std":"1 이상", "meas":"3", "result":"양호", "note":""},
    ],
    "티튜브": [
        {"target":"[MJB-1]", "desc":"DC1000V FUSE15A / 1CH~19CH", "v":"DC 789", "std":"1 이상", "meas":"250", "result":"양호", "note":""},
        {"target":"[MJB-2]", "desc":"DC1000V FUSE15A / 1CH~19CH", "v":"DC 792", "std":"1 이상", "meas":"300", "result":"양호", "note":""},
        {"target":"[MJB-3]", "desc":"DC1000V FUSE15A / 1CH~18CH", "v":"DC 792", "std":"1 이상", "meas":"300", "result":"양호", "note":""},
        {"target":"[MJB-4]", "desc":"DC1000V FUSE15A / 1CH~11CH", "v":"DC 792", "std":"1 이상", "meas":"300", "result":"양호", "note":""},
        {"target":"[MJB-5]", "desc":"DC1000V FUSE15A / 1CH~16CH", "v":"DC 791", "std":"1 이상", "meas":"300", "result":"양호", "note":""},
        {"target":"[MJB-6]", "desc":"DC1000V FUSE15A / 1CH~15CH", "v":"DC 795", "std":"1 이상", "meas":"250", "result":"양호", "note":""},
        {"target":"[MJB-7]", "desc":"DC1000V FUSE15A / 1CH~16CH", "v":"DC 790", "std":"1 이상", "meas":"250", "result":"양호", "note":""},
        {"target":"[MJB-8]", "desc":"DC1000V FUSE15A / 1CH~12CH", "v":"DC 794", "std":"1 이상", "meas":"300", "result":"양호", "note":""},
    ],
}

B10_DATA = {
    "비축기지": [
        {"target":"[MJB-1]", "v":"DC 789", "std":"10 이하", "meas":"0.08", "result":"양호", "note":""},
        {"target":"[MJB-2]", "v":"DC 792", "std":"10 이하", "meas":"0.09", "result":"양호", "note":""},
        {"target":"[MJB-3]", "v":"DC 792", "std":"10 이하", "meas":"0.09", "result":"양호", "note":""},
        {"target":"[MJB-4]", "v":"DC 792", "std":"10 이하", "meas":"0.09", "result":"양호", "note":""},
        {"target":"[MJB-5]", "v":"DC 791", "std":"10 이하", "meas":"0.11", "result":"양호", "note":""},
        {"target":"[MJB-6]", "v":"DC 795", "std":"10 이하", "meas":"0.1",  "result":"양호", "note":""},
        {"target":"[MJB-7]", "v":"DC 790", "std":"10 이하", "meas":"0.09", "result":"양호", "note":""},
        {"target":"[MJB-8]", "v":"DC 794", "std":"10 이하", "meas":"0.09", "result":"양호", "note":""},
        {"target":"인버터",  "v":"AC380/220", "std":"10 이하", "meas":"0.09",  "result":"양호", "note":""},
        {"target":"TR 중성점","v":"",         "std":"10 이하", "meas":"0.087", "result":"양호", "note":""},
        {"target":"MOF",     "v":"",          "std":"10 이하", "meas":"0.12",  "result":"양호", "note":""},
        {"target":"3종접지", "v":"",          "std":"100 이하","meas":"11.8",  "result":"양호", "note":""},
    ],
    "티튜브": [
        {"target":"[MJB-1]", "v":"DC 789", "std":"10 이하", "meas":"0.19", "result":"양호", "note":""},
        {"target":"[MJB-2]", "v":"DC 792", "std":"10 이하", "meas":"0.21", "result":"양호", "note":""},
        {"target":"[MJB-3]", "v":"DC 792", "std":"10 이하", "meas":"0.17", "result":"양호", "note":""},
        {"target":"[MJB-4]", "v":"DC 792", "std":"10 이하", "meas":"0.22", "result":"양호", "note":""},
        {"target":"[MJB-5]", "v":"DC 791", "std":"10 이하", "meas":"0.16", "result":"양호", "note":""},
        {"target":"[MJB-6]", "v":"DC 795", "std":"10 이하", "meas":"0.11", "result":"양호", "note":""},
        {"target":"[MJB-7]", "v":"DC 790", "std":"10 이하", "meas":"0.15", "result":"양호", "note":""},
        {"target":"[MJB-8]", "v":"DC 794", "std":"10 이하", "meas":"0.17", "result":"양호", "note":""},
        {"target":"인버터",  "v":"AC380/220", "std":"10 이하", "meas":"1.12", "result":"양호", "note":""},
        {"target":"TR 중성점","v":"",         "std":"10 이하", "meas":"0.11", "result":"양호", "note":""},
        {"target":"MOF",     "v":"",          "std":"10 이하", "meas":"3.0",  "result":"양호", "note":""},
        {"target":"3종접지", "v":"",          "std":"100 이하","meas":"13.3", "result":"양호", "note":""},
    ],
}

B11_DATA = {
    "비축기지": {"place":"옥외","phase":"3 Φ","cap":"1000kVA","v_pri":"22.9","v_sec":"350","company":"㈜효성","ext_check":"O","ins_1d":"4000 이상","ins_2d":"478","ins_1":"4000 이상","ins_2":"4000 이상","result":"양호","note":"내부 점검 이상없음 (산가도 측정은 4년주기로 한다.)"},
    "티튜브":   {"place":"옥외","phase":"3 Φ","cap":"1000kVA","v_pri":"22.9","v_sec":"350","company":"㈜효성","ext_check":"O","ins_1d":"4000 이상","ins_2d":"1080","ins_1":"4000 이상","ins_2":"4000 이상","result":"양호","note":"내부 점검 이상없음 (산가도 측정은 4년주기로 한다.)"},
}


def _overlay_overrides(img, page, sx, sy, overrides):
    """PDF span을 찾아 overrides({old_text: new_text})로 교체."""
    if not overrides: return
    d = ImageDraw.Draw(img)
    all_spans = []
    for blk in page.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            for sp in ln.get("spans", []):
                if sp["text"].strip():
                    all_spans.append({"text":sp["text"].strip(), "bbox":sp["bbox"], "size":sp["size"]})
    for old_text, new_text in overrides.items():
        if not new_text or not str(new_text).strip(): continue
        new_text = str(new_text).strip()
        if old_text == new_text: continue
        for sp in all_spans:
            if sp["text"] == old_text:
                bb = sp["bbox"]; pad = 2
                d.rectangle([bb[0]*sx-pad, bb[1]*sy-pad, bb[2]*sx+pad+40, bb[3]*sy+pad], fill="white")
                size_px = int(sp["size"] * sy * 0.95)
                _draw_mixed(d, bb[0]*sx, bb[1]*sy - 1, new_text, size_px)
                break


def render_b9(site_name: str, overrides: dict = None, photo_paths: list = None) -> "Image.Image":
    pdf_path = _template_pdf_path("b9", site_name)
    if not os.path.exists(pdf_path):
        return Image.new("RGB", (2481, 3509), "white")
    img, page, doc, sx, sy = _render_pdf_page_to_img(pdf_path)
    try: _overlay_overrides(img, page, sx, sy, overrides)
    except Exception as _e: print(f"[WARN] b9 overlay: {_e!r}")
    # 사진 1장 — 하단 중앙 (기존 PDF 사진 영역 정확히 덮어쓰기)
    try:
        if photo_paths and len(photo_paths) > 0 and photo_paths[0] and os.path.exists(photo_paths[0]):
            W_img, H_img = img.size
            # PDF 사진 위치: 중앙 50% 너비, 60~80% 높이 영역
            ph_w = int(W_img * 0.5); ph_h = int(H_img * 0.2)
            ph_x = (W_img - ph_w) // 2; ph_y = int(H_img * 0.62)
            try:
                p = Image.open(photo_paths[0]).convert("RGB")
                p.thumbnail((ph_w, ph_h), Image.LANCZOS)
                # 흰색 배경으로 덮고 사진 paste
                d_ = ImageDraw.Draw(img)
                d_.rectangle([ph_x-2, ph_y-2, ph_x+ph_w+2, ph_y+ph_h+2], fill="white")
                px_off = ph_x + (ph_w - p.width) // 2
                py_off = ph_y + (ph_h - p.height) // 2
                img.paste(p, (px_off, py_off))
            except Exception as _pe: print(f"[WARN] b9 photo paste: {_pe!r}")
    except Exception as _e: print(f"[WARN] b9 photo: {_e!r}")
    doc.close()
    return img


def render_b10(site_name: str, overrides: dict = None, photo_paths: list = None) -> "Image.Image":
    pdf_path = _template_pdf_path("b10", site_name)
    if not os.path.exists(pdf_path):
        return Image.new("RGB", (2481, 3509), "white")
    img, page, doc, sx, sy = _render_pdf_page_to_img(pdf_path)
    try: _overlay_overrides(img, page, sx, sy, overrides)
    except Exception as _e: print(f"[WARN] b10 overlay: {_e!r}")
    # 사진 3장 — 표 아래 가로 3분할 (페이지 안쪽)
    try:
        if photo_paths:
            W_img, H_img = img.size
            # 표 끝 ~ 페이지 하단 사이 (페이지 잘림 방지)
            ph_h = int(H_img * 0.13)
            ph_w = int(W_img * 0.28)
            ph_y = int(H_img * 0.72)
            d_ = ImageDraw.Draw(img)
            for i, pp in enumerate(photo_paths[:3]):
                if not pp or not os.path.exists(pp): continue
                ph_x = int(W_img * 0.05) + i * (ph_w + int(W_img * 0.025))
                try:
                    p = Image.open(pp).convert("RGB")
                    p.thumbnail((ph_w, ph_h), Image.LANCZOS)
                    d_.rectangle([ph_x-2, ph_y-2, ph_x+ph_w+2, ph_y+ph_h+2], fill="white")
                    px_off = ph_x + (ph_w - p.width) // 2
                    py_off = ph_y + (ph_h - p.height) // 2
                    img.paste(p, (px_off, py_off))
                except Exception as _pe: print(f"[WARN] b10 photo {i} paste: {_pe!r}")
    except Exception as _e: print(f"[WARN] b10 photo: {_e!r}")
    doc.close()
    return img


def render_b11(site_name: str, overrides: dict = None) -> "Image.Image":
    pdf_path = _template_pdf_path("b11", site_name)
    if not os.path.exists(pdf_path):
        return Image.new("RGB", (2481, 3509), "white")
    img, page, doc, sx, sy = _render_pdf_page_to_img(pdf_path)
    try: _overlay_overrides(img, page, sx, sy, overrides)
    except Exception as _e: print(f"[WARN] b11 overlay: {_e!r}")
    doc.close()
    return img


# v125 — 붙임5 페이지2 (비축/티튜브만, MJB-5/MJB-6 등 추가 컬럼)
B5P2_STRUCTURE = {
    "비축기지": {
        "mjbs": ["MJB-5", "MJB-6"],
        "channels": [str(i) for i in range(1, 13)],
        "states": ["과열 유무", "자동소화장치 상태", "SPD상태", "FUSE단선유무", "외함접지",
                   "볼트풀림유무", "모듈접지선접속상태", "모듈파손유무(육안)", "통신모듈 상태"],
    },
    "티튜브": {
        "mjbs": ["MJB-5", "MJB-6", "MJB-7", "MJB-8"],
        "channels": [str(i) for i in range(1, 17)],
        "states": ["과열 유무", "자동소화장치 상태", "SPD상태", "FUSE단선유무", "외함접지",
                   "볼트풀림유무", "모듈접지선접속상태", "모듈파손유무(육안)", "통신모듈 상태"],
    },
}


def render_b5p2(site_name: str, currents: dict = None, states: dict = None) -> "Image.Image":
    """붙임5 페이지2 — 비축/티튜브 추가 MJB(5/6/7/8) 정보."""
    pdf_path = _template_pdf_path("b5p2", site_name)
    if not os.path.exists(pdf_path):
        return Image.new("RGB", (2481, 3509), "white")
    img, page, doc, sx, sy = _render_pdf_page_to_img(pdf_path)
    try:
        d = ImageDraw.Draw(img)
        struct = B5P2_STRUCTURE.get(site_name)
        if not struct: doc.close(); return img
        import re as _re
        all_spans = []
        for blk in page.get_text("dict")["blocks"]:
            for ln in blk.get("lines", []):
                for sp in ln.get("spans", []):
                    if sp["text"].strip():
                        all_spans.append({
                            "text": sp["text"].strip(),
                            "x0": sp["bbox"][0], "x1": sp["bbox"][2],
                            "y0": sp["bbox"][1], "y1": sp["bbox"][3],
                            "yc": (sp["bbox"][1]+sp["bbox"][3])/2,
                            "xc": (sp["bbox"][0]+sp["bbox"][2])/2,
                            "size": sp["size"], "bbox": sp["bbox"],
                        })
        mjb_spans = [s for s in all_spans if s["text"] in struct["mjbs"]]
        mjb_spans.sort(key=lambda x: x["x0"])
        mjb_xcs = [m["xc"] for m in mjb_spans]
        ch_x_max = mjb_spans[0]["x0"] - 20 if mjb_spans else 150
        ch_spans = [s for s in all_spans
                    if s["text"] in struct["channels"] and s["x0"] < ch_x_max and s["y0"] > 100]
        ch_spans.sort(key=lambda x: x["y0"])
        ch_y_map = {s["text"]: s["yc"] for s in ch_spans}
        curr_spans = [s for s in all_spans
                      if _re.match(r'^\d+(\.\d+)?\s*A$', s["text"]) and s["x0"] > 150]
        def find_curr(ch_str, mjb_idx):
            yc_target = ch_y_map.get(ch_str)
            if yc_target is None or mjb_idx >= len(mjb_xcs): return None
            mxc = mjb_xcs[mjb_idx]
            best, best_d = None, 999
            for cs in curr_spans:
                if abs(cs["yc"] - yc_target) < 6:
                    dx = abs(cs["xc"] - mxc)
                    if dx < best_d: best_d, best = dx, cs
            return best
        for key, new_v in (currents or {}).items():
            if not new_v or not str(new_v).strip(): continue
            try: ch_str, mjb_str = key.split("_"); mjb_idx = int(mjb_str)
            except: continue
            sp = find_curr(ch_str, mjb_idx)
            if not sp: continue
            bb = sp["bbox"]; pad = 2
            d.rectangle([bb[0]*sx-pad, bb[1]*sy-pad, bb[2]*sx+pad, bb[3]*sy+pad], fill="white")
            size_px = int(sp["size"] * sy * 0.95)
            _draw_mixed(d, bb[0]*sx, bb[1]*sy - 1, str(new_v).strip(), size_px)
        state_y_map = {}
        for st_label in struct["states"]:
            for s in all_spans:
                if s["text"] == st_label and s["x0"] < 150:
                    state_y_map[st_label] = s["yc"]; break
        circle_spans = [s for s in all_spans if s["text"] in ("○","O","X","/") and s["x0"] > 150]
        def find_state(state_label, mjb_idx):
            yc_target = state_y_map.get(state_label)
            if yc_target is None or mjb_idx >= len(mjb_xcs): return None
            mxc = mjb_xcs[mjb_idx]
            best, best_d = None, 999
            for cs in circle_spans:
                if abs(cs["yc"] - yc_target) < 6:
                    dx = abs(cs["xc"] - mxc)
                    if dx < best_d: best_d, best = dx, cs
            return best
        for key, new_v in (states or {}).items():
            if not new_v or not str(new_v).strip(): continue
            try: st_idx_str, mjb_str = key.split("_"); st_idx = int(st_idx_str); mjb_idx = int(mjb_str)
            except: continue
            if st_idx >= len(struct["states"]): continue
            sp = find_state(struct["states"][st_idx], mjb_idx)
            if not sp or sp["text"] == str(new_v).strip(): continue
            bb = sp["bbox"]; pad = 2
            d.rectangle([bb[0]*sx-pad, bb[1]*sy-pad, bb[2]*sx+pad, bb[3]*sy+pad], fill="white")
            size_px = int(sp["size"] * sy * 0.95)
            _draw_mixed(d, bb[0]*sx, bb[1]*sy - 1, str(new_v).strip(), size_px)
    except Exception as _e:
        print(f"[WARN] render_b5p2 실패: {_e!r}")
    doc.close()
    return img


# v122 — 붙임5 사이트별 구조 (MJB 컬럼 / 채널 / 상태 라벨)
B5_STRUCTURE = {
    "조달청 청사": {
        "mjbs": ["MJB-1A", "MJB-1B"],
        "channels": ["1", "2", "3", "4", "5", "6"],
        "states": ["과열 유무", "SPD상태", "FUSE단선유무", "외함접지", "볼트풀림유무",
                   "모듈접지선접속상태", "모듈파손유무(육안)", "통신모듈 상태"],
    },
    "비축기지": {
        "mjbs": ["MJB-1", "MJB-2", "MJB-3", "MJB-4"],
        "channels": [str(i) for i in range(1, 21)],
        "states": ["과열 유무", "자동소화장치 상태", "SPD상태", "FUSE단선유무", "외함접지",
                   "볼트풀림유무", "모듈접지선접속상태", "모듈파손유무(육안)", "통신모듈 상태"],
    },
    "티튜브": {
        "mjbs": ["MJB-1", "MJB-2", "MJB-3", "MJB-4"],
        "channels": [str(i) for i in range(1, 20)],
        "states": ["과열 유무", "자동소화장치 상태", "SPD상태", "FUSE단선유무", "외함접지",
                   "볼트풀림유무", "모듈접지선접속상태", "모듈파손유무(육안)", "통신모듈 상태"],
    },
}


def render_b5(site_name: str, currents: dict = None, states: dict = None) -> "Image.Image":
    """붙임5 — 접속반별 전류측정/상태점검. 셀 단위 편집.
    currents: {"<ch>_<mjb_idx>": "X.XX A"} — 채널×MJB 행렬
    states:   {"<state_idx>_<mjb_idx>": "O" | "X" | "/"}
    """
    pdf_path = _template_pdf_path("b5", site_name)
    if not os.path.exists(pdf_path):
        return Image.new("RGB", (2481, 3509), "white")
    img, page, doc, sx, sy = _render_pdf_page_to_img(pdf_path)
    try:
        d = ImageDraw.Draw(img)
        struct = B5_STRUCTURE.get(site_name)
        if not struct: doc.close(); return img
        # 모든 span 수집
        all_spans = []
        for blk in page.get_text("dict")["blocks"]:
            for ln in blk.get("lines", []):
                for sp in ln.get("spans", []):
                    if sp["text"].strip():
                        all_spans.append({
                            "text": sp["text"].strip(),
                            "x0": sp["bbox"][0], "x1": sp["bbox"][2],
                            "y0": sp["bbox"][1], "y1": sp["bbox"][3],
                            "yc": (sp["bbox"][1]+sp["bbox"][3])/2,
                            "xc": (sp["bbox"][0]+sp["bbox"][2])/2,
                            "size": sp["size"], "bbox": sp["bbox"],
                        })
        # MJB 컬럼 xc
        import re as _re
        mjb_spans = [s for s in all_spans if s["text"] in struct["mjbs"]]
        mjb_spans.sort(key=lambda x: x["x0"])
        mjb_xcs = [m["xc"] for m in mjb_spans]
        # 채널 행 (좌측 1~2자리 숫자)
        ch_x_max = mjb_spans[0]["x0"] - 20 if mjb_spans else 150
        ch_spans = [s for s in all_spans
                    if s["text"] in struct["channels"] and s["x0"] < ch_x_max and s["y0"] > 100]
        ch_spans.sort(key=lambda x: x["y0"])
        ch_y_map = {s["text"]: s["yc"] for s in ch_spans}
        # 전류 값 (X.XX A 또는 XA)
        curr_spans = [s for s in all_spans
                      if _re.match(r'^\d+(\.\d+)?\s*A$', s["text"]) and s["x0"] > 150]
        def find_curr(ch_str, mjb_idx):
            yc_target = ch_y_map.get(ch_str)
            if yc_target is None or mjb_idx >= len(mjb_xcs): return None
            mxc = mjb_xcs[mjb_idx]
            best, best_d = None, 999
            for cs in curr_spans:
                if abs(cs["yc"] - yc_target) < 6:
                    dx = abs(cs["xc"] - mxc)
                    if dx < best_d: best_d, best = dx, cs
            return best
        currents = currents or {}
        for key, new_v in currents.items():
            if not new_v or not str(new_v).strip(): continue
            try: ch_str, mjb_str = key.split("_")
            except: continue
            try: mjb_idx = int(mjb_str)
            except: continue
            sp = find_curr(ch_str, mjb_idx)
            if not sp: continue
            bb = sp["bbox"]
            pad = 2
            d.rectangle([bb[0]*sx-pad, bb[1]*sy-pad, bb[2]*sx+pad, bb[3]*sy+pad], fill="white")
            size_px = int(sp["size"] * sy * 0.95)
            _draw_mixed(d, bb[0]*sx, bb[1]*sy - 1, str(new_v).strip(), size_px)
        # 상태 ○ 매트릭스
        state_y_map = {}
        for st_label in struct["states"]:
            for s in all_spans:
                if s["text"] == st_label and s["x0"] < 150:
                    state_y_map[st_label] = s["yc"]; break
        circle_spans = [s for s in all_spans if s["text"] in ("○","O","X","/") and s["x0"] > 150]
        def find_state(state_label, mjb_idx):
            yc_target = state_y_map.get(state_label)
            if yc_target is None or mjb_idx >= len(mjb_xcs): return None
            mxc = mjb_xcs[mjb_idx]
            best, best_d = None, 999
            for cs in circle_spans:
                if abs(cs["yc"] - yc_target) < 6:
                    dx = abs(cs["xc"] - mxc)
                    if dx < best_d: best_d, best = dx, cs
            return best
        states = states or {}
        for key, new_v in states.items():
            if not new_v or not str(new_v).strip(): continue
            try: st_idx_str, mjb_str = key.split("_")
            except: continue
            try: st_idx = int(st_idx_str); mjb_idx = int(mjb_str)
            except: continue
            if st_idx >= len(struct["states"]): continue
            sp = find_state(struct["states"][st_idx], mjb_idx)
            if not sp: continue
            if sp["text"] == str(new_v).strip(): continue
            bb = sp["bbox"]
            pad = 2
            d.rectangle([bb[0]*sx-pad, bb[1]*sy-pad, bb[2]*sx+pad, bb[3]*sy+pad], fill="white")
            size_px = int(sp["size"] * sy * 0.95)
            _draw_mixed(d, bb[0]*sx, bb[1]*sy - 1, str(new_v).strip(), size_px)
    except Exception as _e:
        print(f"[WARN] render_b5 편집 적용 실패: {_e!r}")
    doc.close()
    return img


B6_ROW_LABELS = [
    "1. 출력 — 일사량 대비 출력", "2. 외관 — 변색(황변/백화)",
    "3. 외관 — 적외선열화상 핫스팟", "4. 외관 — 프레임 부식",
    "5. 음영 — 어레이 주변 음영", "6. 본딩 — 모듈과 지지대 접속",
    "7. 기초상태 — 결속/정착", "8. 볼트체결 — 풀림방지",
    "9. 접속함 — 외함 부식", "10. 지지물 — 설치상태",
    "11. 도금상태 — 아연도금", "12. 고정 — 모듈 직렬배선",
    "13. 전선연결 — DC케이블", "14. 커넥터 — 빗물 침투방지",
    "15. 외관 — 외함 손상", "16. 작동상태 — 소음/진동/냄새",
    "17. 전선로 — 배선 손상", "18. 설치환경 — 온도/습도/청소",
    "19. 보호값 — 계전기 설정", "20. 부지안전 — 배수시설",
    "21. 부지안전 — 지지대 침하", "22. 부지안전 — 지반 침하",
    "23. 부지안전 — 축대 균열", "24. 구조물 — 지붕/기초",
    "25. 구조물 — 추가 하중",
]


def render_b6(site_name: str, results: list = None, opinion: str = None) -> "Image.Image":
    """붙임6 — 태양광발전설비 점검기록표. 25행 점검결과 + 종합의견 편집."""
    pdf_path = _template_pdf_path("b6", site_name)
    if not os.path.exists(pdf_path):
        return Image.new("RGB", (2481, 3509), "white")
    img, page, doc, sx, sy = _render_pdf_page_to_img(pdf_path)
    try:
        d = ImageDraw.Draw(img)
        all_spans = []
        for blk in page.get_text("dict")["blocks"]:
            for ln in blk.get("lines", []):
                for sp in ln.get("spans", []):
                    if sp["text"].strip():
                        all_spans.append({
                            "text": sp["text"].strip(),
                            "bbox": sp["bbox"],
                            "size": sp["size"],
                        })
        result_spans = [sp for sp in all_spans
                        if sp["text"] in ("O", "○", "X", "x", "/")
                        and sp["bbox"][0] > 450]
        result_spans.sort(key=lambda x: x["bbox"][1])
        if results:
            for i, new_val in enumerate(results):
                if i >= len(result_spans): break
                if not new_val: continue
                nv = str(new_val).strip()
                if not nv: continue
                sp = result_spans[i]
                if sp["text"] == nv: continue
                bb = sp["bbox"]
                pad = 2
                d.rectangle([bb[0]*sx - pad, bb[1]*sy - pad,
                             bb[2]*sx + pad, bb[3]*sy + pad], fill="white")
                size_px = int(sp["size"] * sy * 0.95)
                _draw_mixed(d, bb[0]*sx, bb[1]*sy - 1, nv, size_px)
        if opinion and opinion.strip():
            for sp in all_spans:
                if "절연 및 접지저항 측정" in sp["text"] and "-" in sp["text"]:
                    bb = sp["bbox"]
                    pad = 2
                    d.rectangle([bb[0]*sx - pad, bb[1]*sy - pad,
                                 bb[2]*sx + pad + 200, bb[3]*sy + pad], fill="white")
                    size_px = int(sp["size"] * sy * 0.95)
                    _draw_mixed(d, bb[0]*sx, bb[1]*sy - 1, opinion.strip(), size_px)
                    break
    except Exception as _e:
        print(f"[WARN] render_b6 편집 적용 실패: {_e!r}")
    doc.close()
    return img


# v118 — 붙임4 ACB/MCCB-PANEL 점검기록표: 전압/전류/판정 항목
B4_VOLT_LABELS = {"rs": "R-S", "st": "S-T", "tr": "T-R"}  # x label → row label
B4_CURR_LABELS = {"r": "R", "s": "S", "t": "T"}
B4_RESULT_LABELS = {
    "overheat": "과열 유무",
    "ground":   "접지선 접속",
    "pt_ct":    "PT 및 CT상태",
    "bolt":     "볼트풀림유무",
    "control":  "제어회로",
    "spd":      "SPD상태",
    "meter":    "계측기표시",
    "clean":    "내부청결상태",
}


def render_b4(site_name: str, voltages: dict = None, currents: dict = None,
              results: dict = None) -> "Image.Image":
    """붙임4 — ACB/MCCB-PANEL 점검기록표. 전압/전류/판정 편집.
    voltages: {"rs":"380.5V", "st":..., "tr":...}
    currents: {"r":"65.0A", "s":..., "t":...}
    results:  {"overheat":"양호" | "불량", ...}
    빈 값/None은 원본 유지.
    """
    pdf_path = _template_pdf_path("b4", site_name)
    if not os.path.exists(pdf_path):
        return Image.new("RGB", (2481, 3509), "white")
    img, page, doc, sx, sy = _render_pdf_page_to_img(pdf_path)
    try:
        d = ImageDraw.Draw(img)
        # 모든 span 수집
        all_spans = []
        for blk in page.get_text("dict")["blocks"]:
            for ln in blk.get("lines", []):
                for sp in ln.get("spans", []):
                    if sp["text"].strip():
                        all_spans.append({
                            "text": sp["text"].strip(),
                            "bbox": sp["bbox"],
                            "size": sp["size"],
                        })
        def _find_y(label):
            """라벨의 y중심 반환 (없으면 None)."""
            for sp in all_spans:
                if sp["text"] == label and sp["bbox"][0] < 250:  # 좌측 영역
                    return (sp["bbox"][1] + sp["bbox"][3]) / 2
            return None
        def _replace_value_at(y_center, new_text, x_lo=300, x_hi=420):
            """같은 행의 값 span을 새 텍스트로 교체."""
            for sp in all_spans:
                bb = sp["bbox"]
                sy_c = (bb[1] + bb[3]) / 2
                if abs(sy_c - y_center) < 6 and x_lo < bb[0] < x_hi:
                    pad = 2
                    d.rectangle([bb[0]*sx - pad, bb[1]*sy - pad,
                                 bb[2]*sx + pad, bb[3]*sy + pad], fill="white")
                    size_px = int(sp["size"] * sy * 0.95)
                    _draw_mixed(d, bb[0]*sx, bb[1]*sy - 1, new_text, size_px)
                    return True
            return False
        voltages = voltages or {}
        currents = currents or {}
        results  = results  or {}
        # 전압 R-S / S-T / T-R
        for k, lab in B4_VOLT_LABELS.items():
            v = (voltages.get(k) or "").strip()
            if not v: continue
            yc = _find_y(lab)
            if yc is not None: _replace_value_at(yc, v)
        # 전류 R / S / T (라벨이 단일 글자 — 좌측 작은 영역)
        for k, lab in B4_CURR_LABELS.items():
            v = (currents.get(k) or "").strip()
            if not v: continue
            for sp in all_spans:
                bb = sp["bbox"]
                if sp["text"] == lab and bb[0] < 200 and (bb[2] - bb[0]) < 12:
                    yc = (bb[1] + bb[3]) / 2
                    _replace_value_at(yc, v)
                    break
        # 판정 (양호/불량)
        for k, lab in B4_RESULT_LABELS.items():
            v = (results.get(k) or "").strip()
            if not v: continue
            yc = _find_y(lab)
            if yc is not None: _replace_value_at(yc, v)
    except Exception as _e:
        print(f"[WARN] render_b4 편집 적용 실패: {_e!r}")
    doc.close()
    return img


# v117 — 붙임2 송 수전설비 점검기록표: 사이트별 점검항목 (PDF에 표시되는 순서)
B2_ITEMS = {
    "조달청 청사": ["CT", "MCCB", "SPD", "INVERTER", "전선,케이블", "기타설비"],
    "비축기지":   ["CH", "LBS", "LA", "MOF(수전용)", "MOF(송전용)", "PF", "PT", "CT",
                "VCB", "TR", "큐비클", "출입문잠금시설", "계전기", "ACB", "INVERTER",
                "CONDENSER", "축전지", "MCCB", "전선,케이블", "정류기반", "기타시설"],
    "티튜브":     ["CH", "LBS", "LA", "MOF(수전용)", "MOF(송전용)", "PF", "PT", "CT",
                "VCB", "TR", "큐비클", "출입문잠금시설", "계전기", "ACB", "INVERTER",
                "CONDENSER", "축전지", "MCCB", "전선,케이블", "정류기반", "기타시설"],
}


def render_b2(site_name: str, results: dict = None, actions: dict = None) -> "Image.Image":
    """붙임2 — 송수전설비 점검기록표. 항목별 점검결과(○/X) 및 조치사항 편집.
    results: {"CT": "X", ...} — ○를 X로 변경할 항목.
    actions: {"CT": "단자체크", ...} — 조치사항 칸에 추가할 텍스트.
    """
    pdf_path = _template_pdf_path("b2", site_name)
    if not os.path.exists(pdf_path):
        return Image.new("RGB", (2481, 3509), "white")
    img, page, doc, sx, sy = _render_pdf_page_to_img(pdf_path)
    try:
        d = ImageDraw.Draw(img)
        items = B2_ITEMS.get(site_name, [])
        # 모든 span 수집 → 항목명 span의 y좌표를 행 기준점으로 사용
        all_spans = []
        for blk in page.get_text("dict")["blocks"]:
            for ln in blk.get("lines", []):
                for sp in ln.get("spans", []):
                    if sp["text"].strip():
                        all_spans.append({
                            "text": sp["text"].strip(),
                            "bbox": sp["bbox"],
                            "size": sp["size"],
                        })
        # 항목별 행 y좌표 찾기
        row_y_by_item = {}
        for it in items:
            for sp in all_spans:
                if sp["text"] == it:
                    row_y_by_item[it] = (sp["bbox"][1] + sp["bbox"][3]) / 2
                    break
        # 점검결과(○) 위치 = 같은 행에서 x가 240~260 영역
        # 조치사항 위치 = 같은 행에서 x가 395 이후
        results = results or {}
        actions = actions or {}
        for it, ycen in row_y_by_item.items():
            new_result = (results.get(it) or "").strip()
            new_action = (actions.get(it) or "").strip()
            if not new_result and not new_action:
                continue
            # 1) 점검결과 ○ → X 변경
            if new_result and new_result in ("X", "x"):
                for sp in all_spans:
                    if sp["text"] == "○":
                        sy_c = (sp["bbox"][1] + sp["bbox"][3]) / 2
                        if abs(sy_c - ycen) < 6 and 235 < sp["bbox"][0] < 270:
                            bb = sp["bbox"]
                            d.rectangle([bb[0]*sx-2, bb[1]*sy-2,
                                         bb[2]*sx+2, bb[3]*sy+2], fill="white")
                            size_px = int(sp["size"] * sy * 0.95)
                            _draw_mixed(d, bb[0]*sx, bb[1]*sy - 1, "X", size_px)
                            break
            # 2) 조치사항 텍스트 추가 (조치사항 컬럼 x=395)
            if new_action:
                size_pt = 10.0
                size_px = int(size_pt * sy * 0.95)
                ax = 395 * sx
                ay = (ycen - size_pt/2 - 2) * sy
                # 기존 빈 영역 위에 그리되, 기존 "세부점검사항은..." 같은 텍스트와 겹치면 그 옆에 덧붙임
                _draw_mixed(d, ax, ay, new_action, size_px)
    except Exception as _e:
        print(f"[WARN] render_b2 편집 적용 실패: {_e!r}")
    doc.close()
    return img



# ============================================================
# 붙임3 인버터 점검기록표 — PDF 템플릿 PNG에 운전상황·점검결과 덮어쓰기
# ============================================================
# 운전상황 7행 (DCV, DCA, ACV, ACA, KW, HZ, 누적발전량) — y 시작 좌표
B3_RUN_ROWS_Y = [1397, 1510, 1623, 1736, 1849, 1962, 2075]   # 끝 = 2188
B3_RUN_KEYS   = ["dcv", "dca", "acv", "aca", "kw", "hz", "cum_mwh"]
B3_RUN_UNITS  = {"dcv":"V", "dca":"A", "acv":"V", "aca":"A", "kw":"kW", "hz":"Hz", "cum_mwh":"MWh"}
# 점검결과 8행 (과열, 접지, 입출력, 출력, FAN, SPD, 필터, 내부청결)
B3_CHK_ROWS_Y = [2188, 2301, 2414, 2527, 2640, 2753, 2866, 2979]  # 끝 = 3090
B3_CHK_KEYS   = ["overheat", "ground", "voltage", "overcurrent", "fan", "spd", "filter", "clean"]
B3_VAL_X1, B3_VAL_X2 = 795, 2185   # 값 셀 x 범위 (좌측 항목명 컬럼 끝 = 794)

def _has_korean(s: str) -> bool:
    for ch in s:
        cp = ord(ch)
        if 0xAC00 <= cp <= 0xD7A3: return True
    return False

def render_b3(site_name: str, run_values: dict, chk_values: dict, page_num: int = 6) -> "Image.Image":
    """붙임3 인버터 점검기록표 — 사이트별 PNG 위에 운전상황+점검결과 덮어쓰기."""
    fn = os.path.join(_PDF_TPL_DIR, f"b3_{site_name}-06.png")
    if not os.path.exists(fn):
        return Image.new("RGB", (2481, 3509), "white")
    img = Image.open(fn).convert("RGB")
    d = ImageDraw.Draw(img)
    # 한글(Droid Sans Fallback)과 영문/숫자(DejaVu Sans)를 글자별로 선택
    SIZE = 32
    try:
        f_kr = ImageFont.truetype(KR_FONT or LATIN_R, SIZE)
    except Exception:
        f_kr = ImageFont.load_default()
    try:
        f_lat = ImageFont.truetype(LATIN_R or KR_FONT, SIZE)
    except Exception:
        f_lat = f_kr

    def _font_for(ch):
        cp = ord(ch)
        # 한글/한자/일본어 → KR; 영문/숫자/기호 → LATIN
        if 0xAC00 <= cp <= 0xD7A3 or 0x3040 <= cp <= 0x30FF or 0x4E00 <= cp <= 0x9FFF:
            return f_kr
        return f_lat

    def _measure(text):
        w = h = 0
        for ch in text:
            fnt = _font_for(ch)
            bb = fnt.getbbox(ch)
            w += bb[2] - bb[0]
            h = max(h, bb[3])
        return w, h

    def fill_row(y_start: int, y_end: int, text: str):
        if not text: return
        d.rectangle([B3_VAL_X1 + 3, y_start + 4, B3_VAL_X2 - 3, y_end - 4], fill="white")
        tw, th = _measure(text)
        cx = (B3_VAL_X1 + B3_VAL_X2) // 2
        cy = (y_start + y_end) // 2
        x = cx - tw // 2
        y = cy - SIZE // 2 - SIZE // 8
        for ch in text:
            fnt = _font_for(ch)
            d.text((x, y), ch, fill="black", font=fnt)
            bb = fnt.getbbox(ch)
            x += bb[2] - bb[0]

    # 운전상황 (값에 단위 자동 부가)
    for i, key in enumerate(B3_RUN_KEYS):
        y1 = B3_RUN_ROWS_Y[i]
        y2 = B3_RUN_ROWS_Y[i + 1] if i + 1 < len(B3_RUN_ROWS_Y) else 2188
        raw = run_values.get(key, "") if run_values else ""
        v = (raw.strip() if isinstance(raw, str) else str(raw)).strip()
        if v:
            unit = B3_RUN_UNITS.get(key, "")
            # 이미 단위로 끝나면 그대로, 아니면 부가
            if unit and not v.lower().endswith(unit.lower()):
                v = f"{v}{unit}"
            fill_row(y1, y2, v)
    # 점검결과
    for i, key in enumerate(B3_CHK_KEYS):
        y1 = B3_CHK_ROWS_Y[i]
        y2 = B3_CHK_ROWS_Y[i + 1] if i + 1 < len(B3_CHK_ROWS_Y) else 3090
        v = chk_values.get(key, "") if chk_values else ""
        if v:
            fill_row(y1, y2, str(v))
    return img


SITE_PRESETS = {   '조달청 청사': {   'voltage_default': '380/220V',
                  'blocks': [   {   'target': '수변전실',
                                    'voltage': '380/220V',
                                    'condition': '외기 19.4°C',
                                    'upper_label': 'CT',
                                    'upper_pts': [19.3, 19.3, 19.1],
                                    'lower_label': 'MCCB',
                                    'lower_pts': [25.1, 23.7, 24.5]},
                                {   'target': '인버터',
                                    'voltage': '380/220V',
                                    'condition': '외기 19.4°C',
                                    'upper_label': '인버터',
                                    'upper_pts': [18.7, None, None],
                                    'lower_label': '',
                                    'lower_pts': [None, None, None]},
                                {   'target': '태양광셀단자함',
                                    'voltage': '720V',
                                    'condition': '외기 19.4°C',
                                    'upper_label': 'MJB-1A 차단기',
                                    'upper_pts': [25.7, 23.1, None],
                                    'lower_label': 'MJB-1A',
                                    'lower_pts': [19.6, 20.4, None]},
                                {   'target': '태양광셀단자함',
                                    'voltage': '720V',
                                    'condition': '외기 19.4°C',
                                    'upper_label': 'MJB-1B 차단기',
                                    'upper_pts': [20.6, 20, None],
                                    'lower_label': 'MJB-1B',
                                    'lower_pts': [25.8, 24.9, None]}],
                  'b8_captions': [   ['수변전실 외관', 'MCCB 패널', '접지단자 점검', '차단기 점검'],
                                     ['기상반 외관', '인버터 외관', 'DC 단자함 점검', 'AC 단자함 점검']]},
    '비축기지': {   'voltage_default': '22,900V',
                'blocks': [   {   'target': '수변전실',
                                  'voltage': '22,900V',
                                  'condition': '외기 12.7°C',
                                  'upper_label': 'CH',
                                  'upper_pts': [26.8, 26.8, 27.2],
                                  'lower_label': 'LBS',
                                  'lower_pts': [27.4, 27.5, 27.7]},
                              {   'target': '수변전실',
                                  'voltage': '22,900V',
                                  'condition': '외기 12.7°C',
                                  'upper_label': 'POWER FUSE',
                                  'upper_pts': [35.1, 36, 36.1],
                                  'lower_label': 'LA',
                                  'lower_pts': [26.2, 26.1, 26.3]},
                              {   'target': '수변전실',
                                  'voltage': '22,900V',
                                  'condition': '외기 12.7°C',
                                  'upper_label': 'MOF',
                                  'upper_pts': [25.9, 25.9, 25.9],
                                  'lower_label': 'PT',
                                  'lower_pts': [27.1, 23.9, 28.8]},
                              {   'target': '수변전실',
                                  'voltage': '22,900V',
                                  'condition': '외기 12.7°C',
                                  'upper_label': 'CT',
                                  'upper_pts': [24.6, 24.3, 24.2],
                                  'lower_label': 'VCB',
                                  'lower_pts': [25.9, None, None]},
                              {   'target': '수변전실',
                                  'voltage': '22,900V',
                                  'condition': '외기 12.7°C',
                                  'upper_label': 'TR',
                                  'upper_pts': [38.2, 35.2, 38.9],
                                  'lower_label': 'ACB2차',
                                  'lower_pts': [47.5, 48.4, 47.3]},
                              {   'target': '수변전실',
                                  'voltage': '22,900/440V',
                                  'condition': '외기 12.7°C',
                                  'upper_label': 'ACB 1차',
                                  'upper_pts': [59.7, 65, 57.7],
                                  'lower_label': 'INVERTER',
                                  'lower_pts': [44.4, None, None]},
                              {   'target': '변압기,축전지',
                                  'voltage': '350/220V',
                                  'condition': '외기 12.7°C',
                                  'upper_label': '소내용TR',
                                  'upper_pts': [34.7, 38.1, 36.1],
                                  'lower_label': '축전지1~3',
                                  'lower_pts': [23.7, 23.7, None]},
                              {   'target': '축전지',
                                  'voltage': '350/220V',
                                  'condition': '외기 12.7°C',
                                  'upper_label': '축전지4~6',
                                  'upper_pts': [24.2, 24.3, None],
                                  'lower_label': '축전지7~9',
                                  'lower_pts': [24.4, 24.8, None]},
                              {   'target': '태양광셀단자함',
                                  'voltage': '720V',
                                  'condition': '외기 12.7°C',
                                  'upper_label': 'MJB-1 차단기',
                                  'upper_pts': [39.1, 38.6, None],
                                  'lower_label': 'MJB-1',
                                  'lower_pts': [47, 39, None]},
                              {   'target': '태양광셀단자함',
                                  'voltage': '720V',
                                  'condition': '외기 12.7°C',
                                  'upper_label': 'MJB-2 차단기',
                                  'upper_pts': [38.2, 42.1, None],
                                  'lower_label': 'MJB-2',
                                  'lower_pts': [47.7, 36.1, None]},
                              {   'target': '태양광셀단자함',
                                  'voltage': '720V',
                                  'condition': '외기 12.7°C',
                                  'upper_label': 'MJB-3 차단기',
                                  'upper_pts': [32.7, 39.5, None],
                                  'lower_label': 'MJB-3',
                                  'lower_pts': [45.4, 38.3, None]},
                              {   'target': '태양광셀단자함',
                                  'voltage': '720V',
                                  'condition': '외기 12.7°C',
                                  'upper_label': 'MJB-4 차단기',
                                  'upper_pts': [36.7, 35.5, None],
                                  'lower_label': 'MJB-4',
                                  'lower_pts': [45.4, 38.3, None]},
                              {   'target': '태양광셀단자함',
                                  'voltage': '720V',
                                  'condition': '외기 12.7°C',
                                  'upper_label': 'MJB-5 차단기',
                                  'upper_pts': [34.7, 36.3, None],
                                  'lower_label': 'MJB-5',
                                  'lower_pts': [43.5, 36.1, None]},
                              {   'target': '태양광셀단자함',
                                  'voltage': '720V',
                                  'condition': '외기 12.7°C',
                                  'upper_label': 'MJB-6 차단기',
                                  'upper_pts': [32.3, 33.3, None],
                                  'lower_label': 'MJB-6',
                                  'lower_pts': [42.7, 36.9, None]}],
                'b8_captions': [   ['수변전실 외관', 'VCB 패널', 'MCCB 패널', '접지단자 점검'],
                                   ['축전지실 외관', '인버터 외관', 'MJB 외관', '기상센서함 점검']]},
    '티튜브': {   'voltage_default': '22,900V',
               'blocks': [   {   'target': '수변전실',
                                 'voltage': '22,900V',
                                 'condition': '외기 23.4°C',
                                 'upper_label': 'CH',
                                 'upper_pts': [22.2, 22.2, 21.6],
                                 'lower_label': 'LBS',
                                 'lower_pts': [21.3, 21.6, 21.3]},
                             {   'target': '수변전실',
                                 'voltage': '22,900V',
                                 'condition': '외기 23.4°C',
                                 'upper_label': 'POWER FUSE',
                                 'upper_pts': [28.9, 29.6, 28.8],
                                 'lower_label': 'LA',
                                 'lower_pts': [21.4, 21.6, 21.5]},
                             {   'target': '수변전실',
                                 'voltage': '22,900V',
                                 'condition': '외기 23.4°C',
                                 'upper_label': 'MOF',
                                 'upper_pts': [21.7, 21.7, 21.9],
                                 'lower_label': 'PT',
                                 'lower_pts': [33.2, 33.1, 23.3]},
                             {   'target': '수변전실',
                                 'voltage': '22,900V',
                                 'condition': '외기 23.4°C',
                                 'upper_label': 'CT',
                                 'upper_pts': [21.3, 21.2, 21.1],
                                 'lower_label': 'VCB',
                                 'lower_pts': [21.6, None, None]},
                             {   'target': '수변전실',
                                 'voltage': '22,900V',
                                 'condition': '외기 23.4°C',
                                 'upper_label': 'TR',
                                 'upper_pts': [26.5, 24.1, 26],
                                 'lower_label': 'ACB',
                                 'lower_pts': [24.7, None, None]},
                             {   'target': '수변전실',
                                 'voltage': '22,900V',
                                 'condition': '외기 23.4°C',
                                 'upper_label': 'ACB 1차',
                                 'upper_pts': [32.3, 35.9, 35.1],
                                 'lower_label': 'INVERTER',
                                 'lower_pts': [44.7, None, None]},
                             {   'target': '변압기,축전지',
                                 'voltage': '350/220V',
                                 'condition': '외기 23.4°C',
                                 'upper_label': '소내용TR',
                                 'upper_pts': [28.9, 28.5, 28.3],
                                 'lower_label': '축전지1~3',
                                 'lower_pts': [20.4, 20.3, 20]},
                             {   'target': '축전지',
                                 'voltage': '350/220V',
                                 'condition': '외기 23.4°C',
                                 'upper_label': '축전지4~6',
                                 'upper_pts': [19.4, 20.1, None],
                                 'lower_label': '축전지7~9',
                                 'lower_pts': [20, 19.8, None]},
                             {   'target': '태양광셀단자함',
                                 'voltage': '760V',
                                 'condition': '외기 23.4°C',
                                 'upper_label': 'MJB-1 차단기',
                                 'upper_pts': [18.5, 18.6, None],
                                 'lower_label': 'MJB-1',
                                 'lower_pts': [32.9, 38.5, None]},
                             {   'target': '태양광셀단자함',
                                 'voltage': '760V',
                                 'condition': '외기 23.4°C',
                                 'upper_label': 'MJB-2 차단기',
                                 'upper_pts': [24.3, 24.2, None],
                                 'lower_label': 'MJB-2',
                                 'lower_pts': [34.7, 44.3, None]},
                             {   'target': '태양광셀단자함',
                                 'voltage': '760V',
                                 'condition': '외기 23.4°C',
                                 'upper_label': 'MJB-3 차단기',
                                 'upper_pts': [25.1, 24.5, None],
                                 'lower_label': 'MJB-3',
                                 'lower_pts': [35.2, 41.6, None]},
                             {   'target': '태양광셀단자함',
                                 'voltage': '760V',
                                 'condition': '외기 23.4°C',
                                 'upper_label': 'MJB-4 차단기',
                                 'upper_pts': [24.5, 24.1, None],
                                 'lower_label': 'MJB-4',
                                 'lower_pts': [33.9, 41.4, None]},
                             {   'target': '태양광셀단자함',
                                 'voltage': '760V',
                                 'condition': '외기 23.4°C',
                                 'upper_label': 'MJB-5 차단기',
                                 'upper_pts': [25.8, 25.5, None],
                                 'lower_label': 'MJB-5',
                                 'lower_pts': [35.3, 39.6, None]},
                             {   'target': '태양광셀단자함',
                                 'voltage': '760V',
                                 'condition': '외기 23.4°C',
                                 'upper_label': 'MJB-6 차단기',
                                 'upper_pts': [33.3, 32.7, None],
                                 'lower_label': 'MJB-6',
                                 'lower_pts': [37.3, 40.6, None]},
                             {   'target': '태양광셀단자함',
                                 'voltage': '760V',
                                 'condition': '외기 23.4°C',
                                 'upper_label': 'MJB-7 차단기',
                                 'upper_pts': [26.3, 26.4, None],
                                 'lower_label': 'MJB-7',
                                 'lower_pts': [31, 30.3, None]},
                             {   'target': '태양광셀단자함',
                                 'voltage': '760V',
                                 'condition': '외기 23.4°C',
                                 'upper_label': 'MJB-8 차단기',
                                 'upper_pts': [25.4, 25.9, None],
                                 'lower_label': 'MJB-8',
                                 'lower_pts': [29.6, 29.1, None]}],
               'b8_captions': [   ['수변전실 외관', 'VCB 패널', 'MCCB 패널', '접지단자 점검'],
                                  ['축전지실 외관', '인버터 외관', 'MJB 외관', '기상센서함 점검']]}}


def generate_report_pdf(site_name, blocks, photos, b8_pages, out_path,
                        year_month: str = "", include_cover: bool = True,
                        b3_run: dict = None, b3_chk: dict = None, include_b3: bool = False,
                        inspection_date: str = "", p2_items: list = None, p2_results: list = None,
                        p3_items: list = None,
                        b2_results: dict = None, b2_actions: dict = None,
                        b4_voltages: dict = None, b4_currents: dict = None, b4_results: dict = None,
                        b5_currents: dict = None, b5_states: dict = None,
                        b5p2_currents: dict = None, b5p2_states: dict = None,
                        b6_results: list = None, b6_opinion: str = None,
                        b9_overrides: dict = None, b10_overrides: dict = None, b11_overrides: dict = None,
                        b9_photos: list = None, b10_photos: list = None,
                        include_p2: bool = True, include_p3: bool = True, include_p4: bool = True,
                        include_b1: bool = True, include_b2: bool = True,
                        include_b4: bool = True, include_b5: bool = True, include_b6: bool = True,
                        include_b9: bool = False, include_b10: bool = False, include_b11: bool = False):
    pages = []
    if include_cover:
        try: pages.append(render_cover(site_name, year_month))
        except Exception as _e: print(f"[WARN] cover: {_e}")
    if include_p2:
        try: pages.append(render_p2(site_name, year_month=year_month, inspection_date=inspection_date, items=p2_items, results=p2_results))
        except Exception as _e: print(f"[WARN] p2: {_e}")
    if include_p3:
        try: pages.append(render_p3(site_name, items=p3_items))
        except Exception as _e: print(f"[WARN] p3: {_e}")
    if include_p4 or include_b1:
        try: pages.append(render_p4(site_name))
        except Exception as _e: print(f"[WARN] b1: {_e}")
    if include_b2:
        try: pages.append(render_b2(site_name, results=b2_results, actions=b2_actions))
        except Exception as _e: print(f"[WARN] b2: {_e}")
    if include_b3:
        try: pages.append(render_b3(site_name, b3_run or {}, b3_chk or {}))
        except Exception as _e: print(f"[WARN] b3: {_e}")
    if include_b4:
        try: pages.append(render_b4(site_name, voltages=b4_voltages, currents=b4_currents, results=b4_results))
        except Exception as _e: print(f"[WARN] b4: {_e}")
    if include_b5:
        try: pages.append(render_b5(site_name, currents=b5_currents, states=b5_states))
        except Exception as _e: print(f"[WARN] b5: {_e}")
        if site_name in B5P2_STRUCTURE:
            try: pages.append(render_b5p2(site_name, currents=b5p2_currents, states=b5p2_states))
            except Exception as _e: print(f"[WARN] b5p2: {_e}")
    if include_b6:
        try: pages.append(render_b6(site_name, results=b6_results, opinion=b6_opinion))
        except Exception as _e: print(f"[WARN] b6: {_e}")
    if include_b9 and os.path.exists(_template_pdf_path("b9", site_name)):
        try: pages.append(render_b9(site_name, overrides=b9_overrides, photo_paths=b9_photos))
        except Exception as _e: print(f"[WARN] b9: {_e}")
    if include_b10 and os.path.exists(_template_pdf_path("b10", site_name)):
        try: pages.append(render_b10(site_name, overrides=b10_overrides, photo_paths=b10_photos))
        except Exception as _e: print(f"[WARN] b10: {_e}")
    if include_b11 and os.path.exists(_template_pdf_path("b11", site_name)):
        try: pages.append(render_b11(site_name, overrides=b11_overrides))
        except Exception as _e: print(f"[WARN] b11: {_e}")
    page_num = 1
    for i, blk in enumerate(blocks):
        seed = hash(site_name) % 1000 + i * 10
        photos_for_block = photos.get(i, {}) if isinstance(photos, dict) else {}
        pages.append(render_b7(blk, page_num, photos_for_block, seed=seed))
        page_num += 1
    for items in b8_pages:
        pages.append(render_b8(items, page_num))
        page_num += 1
    if not pages: raise ValueError("PDF empty")
    import gc, io as _io, fitz as _fitz
    A4_PX = (1654, 2339)
    pdf_doc = _fitz.open()
    for idx in range(len(pages)):
        p = pages[idx]
        rgb = p.convert("RGB")
        if rgb.size != A4_PX: rgb = rgb.resize(A4_PX, Image.LANCZOS)
        buf = _io.BytesIO()
        rgb.save(buf, format="JPEG", quality=80, optimize=True)
        jpg_bytes = buf.getvalue()
        del buf, rgb
        new_page = pdf_doc.new_page(width=595, height=842)
        new_page.insert_image(_fitz.Rect(0, 0, 595, 842), stream=jpg_bytes)
        del jpg_bytes
        pages[idx] = None
        gc.collect()
    pages.clear()
    pdf_doc.save(out_path, deflate=True, garbage=4, clean=True)
    pdf_doc.close()
    gc.collect()
    return out_path
