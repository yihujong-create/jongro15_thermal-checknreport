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

# 사이트별 표지 연월 좌표 매핑 (300DPI 기준)
COVER_YM_BOX = {
    "조달청 청사": (1100, 2065, 1380, 2135),
    "비축기지":   (1110, 1895, 1370, 1960),
    "티튜브":     (1110, 1870, 1370, 1935),
}

def _normalize_ym(year_month: str) -> str:
    """'2026.06' / '2026-06' / '2026/6' → '2026. 06'."""
    s = year_month.strip().replace("-", ".").replace("/", ".")
    parts = [p.strip() for p in s.split(".") if p.strip()]
    if len(parts) >= 2:
        return f"{parts[0]}. {parts[1].zfill(2)}"
    return s


def render_cover(site_name: str, year_month: str = "") -> "Image.Image":
    """사이트 표지 PDF의 연월 텍스트만 동적으로 교체한 후 이미지로 렌더링.

    v94 — 원본 PDF를 그대로 사용해서 모든 텍스트/배치/글꼴/테두리가 원본과 완벽 일치.
          연월 부분만 PyMuPDF redact으로 교체.
    year_month: "2026.06" 등. 빈 문자열이면 원본 그대로.
    """
    import fitz
    # 1) PDF 원본 우선 (벡터 품질 유지)
    pdf_path = os.path.join(_PDF_TPL_DIR, f"cover_{site_name}.pdf")
    if os.path.exists(pdf_path):
        doc = fitz.open(pdf_path)
        page = doc[0]
        new_ym = _normalize_ym(year_month) if year_month else ""
        if new_ym:
            # 원본 텍스트에서 "20YY. MM" 패턴 찾기 (이미 정규화 형식)
            target_text = None
            target_bbox = None
            target_size = None
            target_font_xref = None
            for block in page.get_text("dict")["blocks"]:
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        t = span["text"].strip()
                        # "20YY. MM" 또는 "20YY.MM" 형태 (연월만)
                        import re as _re
                        if _re.fullmatch(r"20\d{2}\.\s*\d{1,2}", t):
                            target_text = t
                            target_bbox = fitz.Rect(*span["bbox"])
                            target_size = span["size"]
                            target_font_xref = block  # not used
                            break
                    if target_text:
                        break
                if target_text:
                    break

            if target_bbox is not None:
                # 폰트 추출 (원본 페이지의 동일 폰트 사용)
                cover_font_path = None
                fonts = page.get_fonts()
                # 해당 span이 어느 font를 쓰는지 찾기
                target_font_name = None
                for block in page.get_text("dict")["blocks"]:
                    if "lines" not in block:
                        continue
                    for line in block["lines"]:
                        for span in line["spans"]:
                            if span["text"].strip() == target_text:
                                target_font_name = span["font"]
                                break
                # CIDFont+F1 등 → page.get_fonts에서 매칭 후 추출
                for xref, ext, ftype, fname, fpref, fenc in fonts:
                    if fname == target_font_name:
                        _, _, _, content = doc.extract_font(xref)
                        cover_font_path = os.path.join(_PDF_TPL_DIR, f"_extracted_{fname}.ttf")
                        with open(cover_font_path, "wb") as _ff:
                            _ff.write(content)
                        break

                # 원본 텍스트 위에 흰 사각형 (redact)
                pad = 1.0
                white_rect = fitz.Rect(target_bbox.x0 - pad, target_bbox.y0 - pad,
                                       target_bbox.x1 + pad, target_bbox.y1 + pad)
                page.draw_rect(white_rect, color=(1, 1, 1), fill=(1, 1, 1))

                # 새 연월 텍스트 삽입 — 같은 폰트, 같은 크기, 같은 위치
                try:
                    if cover_font_path:
                        page.insert_font(fontname="cf1", fontfile=cover_font_path)
                        font_name = "cf1"
                    else:
                        font_name = "helv"
                    # 텍스트를 원본과 같은 박스 중앙에 배치
                    # baseline = bbox.y1 (PDF text origin은 baseline)
                    # 원본 텍스트 너비 측정해서 같은 위치 (왼쪽 정렬 유지)
                    page.insert_text(
                        (target_bbox.x0, target_bbox.y0 + target_size),
                        new_ym,
                        fontname=font_name,
                        fontsize=target_size,
                        color=(0, 0, 0),
                    )
                except Exception as e:
                    print(f"[WARN] cover insert_text 실패: {e!r}")

        # 2) 렌더링 — A4 2481x3509에 맞춰 스케일
        scale_x = 2481 / page.rect.width
        scale_y = 3509 / page.rect.height
        pix = page.get_pixmap(matrix=fitz.Matrix(scale_x, scale_y))
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGB")
        # 정확한 2481x3509로 리사이즈 (소수점 차이 보정)
        if img.size != (2481, 3509):
            img = img.resize((2481, 3509), Image.LANCZOS)
        doc.close()
        return img

    # 3) PDF 없으면 기존 PNG 폴백
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
    font_path = LATIN_R or KR_FONT
    try:
        font = ImageFont.truetype(font_path, 52)
    except Exception:
        font = ImageFont.load_default()
    bbox = d.textbbox((0, 0), s, font=font)
    tw = bbox[2] - bbox[0]; th = bbox[3] - bbox[1]
    cx = (x1 + x2) // 2; cy = (y1 + y2) // 2
    d.text((cx - tw // 2, cy - th // 2 - bbox[1]), s, fill="black", font=font)
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


# ============================================================
# v95/v96 — 페이지 2/3: 원본 PDF 그대로 사용 + 편집 가능 텍스트만 redact + 교체
# ============================================================
# 기본값 — 사용자가 수정 안 하면 이 값 사용
DEFAULT_P2 = {
    "inspection_date": "",   # "2026년 05월 08일"
    "items": [               # 주요 점검사항 1~6 (고정 기본)
        "1. 특고압 전기설비 외관 점검",
        "2. 적외선 열화상 진단",
        "3. 모듈 외관 점검",
        "4. 전압, 전류, 발전량 등 측정",
        "5. 인버터 판넬 점검",
        "6. 접속반 점검",
    ],
    "results": [             # 점검결과 및 종합의견 1-1 ~ 6-1
        "1-1. 외관 이상없음",
        "2-1. 적외선 열화상진단결과 중점적으로 단자체크 조임부분 이상 없음",
        "3-1. 모듈외관이 손상되거나 오염된 부분은 없음",
        "4-1. 전압 전류, 발전량 측정결과 현장 이상 없음",
        "5-1. 인버터 판넬 이상 없음",
        "6-1. 접속반 이상 없음",
    ],
}


def _extract_page_font(doc, page, target_font_name, save_dir):
    """페이지에서 사용하는 폰트 추출 → ttf 파일 경로 반환."""
    fonts = page.get_fonts()
    for xref, ext, ftype, fname, fpref, fenc in fonts:
        if fname == target_font_name:
            try:
                _, _, _, content = doc.extract_font(xref)
                path = os.path.join(save_dir, f"_extracted_{fname}.ttf")
                with open(path, "wb") as f:
                    f.write(content)
                return path
            except Exception as e:
                print(f"[WARN] font extract fail {fname}: {e}")
                return None
    return None


def _patch_pdf_text(page, doc, replacements):
    """페이지의 특정 텍스트 span을 새 텍스트로 교체.

    replacements: dict mapping original_text → new_text.
    원본 폰트는 subset이라 모든 한글이 안 들어있을 수 있어서,
    안전을 위해 DroidSansFallback(번들된 한글 풀셋) 사용.
    """
    import fitz
    if not replacements:
        return
    # v100 — 모든 글자 지원하는 한글 폰트 사용 (원본 CIDFont는 글리프 부족)
    kr_font_path = None
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "DroidSansFallback.ttf"),
        "/usr/share/fonts-droid-fallback/truetype/DroidSansFallback.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            kr_font_path = c
            break
    extracted_fonts = {}  # font_name → ttf path
    page_dict = page.get_text("dict")
    for block in page_dict["blocks"]:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                orig = span["text"]
                # 원본 텍스트가 replacements에 있으면 (정확히 또는 strip 후 일치)
                new_text = None
                if orig in replacements:
                    new_text = replacements[orig]
                elif orig.strip() in replacements:
                    new_text = replacements[orig.strip()]
                if new_text is None:
                    continue
                if new_text == orig.strip():
                    continue  # 변경 없음
                bbox = fitz.Rect(*span["bbox"])
                font_name = span["font"]
                font_size = span["size"]
                # 원본 텍스트 위에 흰 사각형 (살짝 여유)
                pad = 0.5
                cover_rect = fitz.Rect(bbox.x0 - pad, bbox.y0 - pad,
                                       bbox.x1 + pad, bbox.y1 + pad)
                page.draw_rect(cover_rect, color=(1, 1, 1), fill=(1, 1, 1))
                # v100 — 원본 subset 폰트 대신 DroidSansFallback(풀셋) 사용
                pdf_font = None
                try:
                    if kr_font_path:
                        pdf_font = "drsk"
                        try:
                            page.insert_font(fontname=pdf_font, fontfile=kr_font_path)
                        except Exception:
                            pass
                    else:
                        pdf_font = "helv"
                    # 텍스트 삽입 위치: bbox.x0 + baseline
                    # baseline ≈ bbox.y1 - descent. PDF text origin = baseline
                    # 안전한 baseline: bbox.y0 + font_size * 0.85
                    baseline_y = bbox.y0 + font_size * 0.85
                    page.insert_text(
                        (bbox.x0, baseline_y),
                        new_text,
                        fontname=pdf_font,
                        fontsize=font_size,
                        color=(0, 0, 0),
                    )
                except Exception as e:
                    print(f"[WARN] insert_text fail {orig!r} → {new_text!r}: {e}")


def _pil_kr_font(size_px: int):
    """DroidSansFallback ImageFont (한글)."""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "DroidSansFallback.ttf"),
        "/usr/share/fonts-droid-fallback/truetype/DroidSansFallback.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size_px)
            except Exception:
                continue
    return ImageFont.load_default()


def _pil_ascii_font(size_px: int):
    """DejaVuSans ImageFont (ASCII/숫자)."""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "DejaVuSans.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size_px)
            except Exception:
                continue
    return _pil_kr_font(size_px)


def _draw_mixed(d, x, y, text, size_px, fill="black"):
    """글자별로 한글/ASCII 폰트 선택해서 그리기. 시작 x 픽셀 위치 반환."""
    kr = _pil_kr_font(size_px)
    ascii_f = _pil_ascii_font(size_px)
    for ch in text:
        cp = ord(ch)
        if (0xAC00 <= cp <= 0xD7A3) or (0x3130 <= cp <= 0x318F) or (0x3000 <= cp <= 0x303F):
            f = kr
        else:
            f = ascii_f
        d.text((x, y), ch, font=f, fill=fill)
        bb = f.getbbox(ch)
        x += bb[2] - bb[0]
    return x


def render_p2(site_name: str, year_month: str = "", inspection_date: str = "",
              items: list = None, results: list = None) -> "Image.Image":
    """페이지 2 — 원본 PDF에 편집 가능 텍스트만 덮어쓴 후 이미지로 변환.

    year_month: 표지와 동일한 연월 (자동 동기화)
    inspection_date: '2026년 05월 08일' 형식
    items: 주요 점검사항 6개 리스트 (None이면 기본값)
    results: 점검결과 및 종합의견 6개 리스트 (None이면 기본값)
    """
    import fitz
    pdf_path = os.path.join(_PDF_TPL_DIR, f"p2_{site_name}.pdf")
    if not os.path.exists(pdf_path):
        return Image.new("RGB", (2481, 3509), "white")
    doc = fitz.open(pdf_path)
    page = doc[0]

    # 교체할 텍스트 매핑 (원본 → 새 텍스트)
    replacements = {}
    # 점검일
    orig_date_candidates = [s for s in [
        "2026년 05월 08일", "2026년 04월 08일", "2026년 05월 09일", "2026년 04월 09일",
    ]]
    if inspection_date:
        # 페이지 내 "20XX년 XX월 XX일" 패턴 찾아서 교체
        for block in page.get_text("dict")["blocks"]:
            if "lines" not in block: continue
            for line in block["lines"]:
                for span in line["spans"]:
                    t = span["text"].strip()
                    import re as _re
                    if _re.fullmatch(r"20\d{2}년\s*\d{1,2}월\s*\d{1,2}일", t):
                        replacements[t] = inspection_date
    # year_month (페이지 2에도 있음)
    if year_month:
        new_ym = _normalize_ym(year_month)
        for block in page.get_text("dict")["blocks"]:
            if "lines" not in block: continue
            for line in block["lines"]:
                for span in line["spans"]:
                    t = span["text"].strip()
                    import re as _re
                    if _re.fullmatch(r"20\d{2}\.\s*\d{1,2}", t):
                        replacements[t] = new_ym
    # 주요 점검사항 1~6 (기존 위치)
    use_items = list(items) if items else [None]*10
    while len(use_items) < 10: use_items.append(None)
    for i, orig in enumerate(DEFAULT_P2["items"]):
        new = use_items[i]
        if new and new != orig:
            replacements[orig] = new
    # 점검결과 1-1 ~ 6-1
    use_results = list(results) if results else [None]*10
    while len(use_results) < 10: use_results.append(None)
    for i, orig in enumerate(DEFAULT_P2["results"]):
        new = use_results[i]
        if new and new != orig:
            replacements[orig] = new

    # v100 — PyMuPDF text 삽입 비활성화 (폰트 글리프 문제 회피)
    # 1) 원본 PDF를 그대로 이미지로 렌더링
    scale_x = 2481 / page.rect.width
    scale_y = 3509 / page.rect.height
    pix = page.get_pixmap(matrix=fitz.Matrix(scale_x, scale_y))
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGB")
    if img.size != (2481, 3509):
        img = img.resize((2481, 3509), Image.LANCZOS)

    # 2) PIL로 redact + 새 텍스트 그리기 (DroidSansFallback로 한글/ASCII 모두 OK)
    d = ImageDraw.Draw(img)
    page_dict = page.get_text("dict")
    for block in page_dict["blocks"]:
        if "lines" not in block: continue
        for line in block["lines"]:
            for span in line["spans"]:
                orig = span["text"]
                new_text = None
                if orig in replacements: new_text = replacements[orig]
                elif orig.strip() in replacements: new_text = replacements[orig.strip()]
                if new_text is None or new_text == orig.strip(): continue
                bbox = span["bbox"]
                size_pt = span["size"]
                pad = 2
                x1 = bbox[0] * scale_x - pad
                y1 = bbox[1] * scale_y - pad
                x2 = bbox[2] * scale_x + pad
                y2 = bbox[3] * scale_y + pad
                d.rectangle([x1, y1, x2, y2], fill="white")
                size_px = int(size_pt * scale_y * 0.95)
                _draw_mixed(d, bbox[0] * scale_x, bbox[1] * scale_y - 1, new_text, size_px)

    # 3) 추가 항목 7~10 / 결과 7-1~10-1
    items_x_pdf = 192.5
    items_y_start = 272.6
    items_dy = 12.9
    items_size_pt = 10.6
    results_y_start = 447.5
    size_px_extra = int(items_size_pt * scale_y * 0.95)
    for i in range(6, 10):
        txt = use_items[i]
        if txt:
            x = items_x_pdf * scale_x
            y = (items_y_start + i * items_dy) * scale_y
            _draw_mixed(d, x, y, txt, size_px_extra)
    for i in range(6, 10):
        txt = use_results[i]
        if txt:
            x = items_x_pdf * scale_x
            y = (results_y_start + i * items_dy) * scale_y
            _draw_mixed(d, x, y, txt, size_px_extra)

    doc.close()
    return img


def _render_static_page(site_name: str, prefix: str) -> "Image.Image":
    """원본 PDF 페이지를 그대로 이미지로 반환 (편집 없음)."""
    import fitz
    pdf_path = os.path.join(_PDF_TPL_DIR, f"{prefix}_{site_name}.pdf")
    if not os.path.exists(pdf_path):
        return Image.new("RGB", (2481, 3509), "white")
    doc = fitz.open(pdf_path)
    page = doc[0]
    scale_x = 2481 / page.rect.width
    scale_y = 3509 / page.rect.height
    pix = page.get_pixmap(matrix=fitz.Matrix(scale_x, scale_y))
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGB")
    if img.size != (2481, 3509):
        img = img.resize((2481, 3509), Image.LANCZOS)
    doc.close()
    return img


def render_p3(site_name: str) -> "Image.Image":
    """페이지 3 (붙임 서류 목록) — 원본 그대로."""
    return _render_static_page(site_name, "p3")


def render_p4(site_name: str) -> "Image.Image":
    """페이지 4 (안전진단장비) — 원본 그대로."""
    return _render_static_page(site_name, "p4")


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


SITE_PRESETS = {
    "조달청 청사": {
        "voltage_default": "380/220V",
        "blocks": [
            {"target": "수변전실", "voltage": "380/220V", "condition": "외기 19.4°C",
             "upper_label": "CT", "upper_pts": [19.3, 19.3, 19.1],
             "lower_label": "MCCB", "lower_pts": [25.1, 23.7, 24.5]},
            {"target": "인버터", "voltage": "380/220V", "condition": "외기 19.4°C",
             "upper_label": "인버터", "upper_pts": [18.7, None, None],
             "lower_label": "", "lower_pts": [None, None, None]},
            {"target": "태양광셀단자함", "voltage": "720V", "condition": "외기 19.4°C",
             "upper_label": "MJB-1A 차단기", "upper_pts": [25.7, 23.1, None],
             "lower_label": "MJB-1A", "lower_pts": [19.6, 20.4, None]},
            {"target": "태양광셀단자함", "voltage": "720V", "condition": "외기 19.4°C",
             "upper_label": "MJB-1B 차단기", "upper_pts": [20.6, 20, None],
             "lower_label": "MJB-1B", "lower_pts": [25.8, 24.9, None]},
        ],
        "b8_captions": [
            ["수변전실 외관", "MCCB 패널", "접지단자 점검", "차단기 점검"],
            ["기상반 외관", "인버터 외관", "DC 단자함 점검", "AC 단자함 점검"],
        ],
    },
    "비축기지": {
        "voltage_default": "22,900V",
        "blocks": [
            {"target": "수변전실", "voltage": "22,900V", "condition": "외기 12.7°C",
             "upper_label": "CH", "upper_pts": [26.8, 26.8, 27.2],
             "lower_label": "LBS", "lower_pts": [27.4, 27.5, 27.7]},
            {"target": "수변전실", "voltage": "22,900V", "condition": "외기 12.7°C",
             "upper_label": "POWER FUSE", "upper_pts": [35.1, 36, 36.1],
             "lower_label": "LA", "lower_pts": [26.2, 26.1, 26.3]},
            {"target": "수변전실", "voltage": "22,900V", "condition": "외기 12.7°C",
             "upper_label": "MOF", "upper_pts": [25.9, 25.9, 25.9],
             "lower_label": "PT", "lower_pts": [27.1, 23.9, 28.8]},
            {"target": "수변전실", "voltage": "22,900V", "condition": "외기 12.7°C",
             "upper_label": "CT", "upper_pts": [24.6, 24.3, 24.2],
             "lower_label": "VCB", "lower_pts": [25.9, None, None]},
            {"target": "수변전실", "voltage": "22,900V", "condition": "외기 12.7°C",
             "upper_label": "TR", "upper_pts": [38.2, 35.2, 38.9],
             "lower_label": "ACB2차", "lower_pts": [47.5, 48.4, 47.3]},
            {"target": "수변전실", "voltage": "22,900/440V", "condition": "외기 12.7°C",
             "upper_label": "ACB 1차", "upper_pts": [59.7, 65, 57.7],
             "lower_label": "INVERTER", "lower_pts": [44.4, None, None]},
            {"target": "변압기,축전지", "voltage": "350/220V", "condition": "외기 12.7°C",
             "upper_label": "소내용TR", "upper_pts": [34.7, 38.1, 36.1],
             "lower_label": "축전지1~3", "lower_pts": [23.7, 23.7, None]},
            {"target": "축전지", "voltage": "350/220V", "condition": "외기 12.7°C",
             "upper_label": "축전지4~6", "upper_pts": [24.2, 24.3, None],
             "lower_label": "축전지7~9", "lower_pts": [24.4, 24.8, None]},
            {"target": "태양광셀단자함", "voltage": "720V", "condition": "외기 12.7°C",
             "upper_label": "MJB-1 차단기", "upper_pts": [39.1, 38.6, None],
             "lower_label": "MJB-1", "lower_pts": [47, 39, None]},
            {"target": "태양광셀단자함", "voltage": "720V", "condition": "외기 12.7°C",
             "upper_label": "MJB-2 차단기", "upper_pts": [38.2, 42.1, None],
             "lower_label": "MJB-2", "lower_pts": [47.7, 36.1, None]},
            {"target": "태양광셀단자함", "voltage": "720V", "condition": "외기 12.7°C",
             "upper_label": "MJB-3 차단기", "upper_pts": [32.7, 39.5, None],
             "lower_label": "MJB-3", "lower_pts": [45.4, 38.3, None]},
            {"target": "태양광셀단자함", "voltage": "720V", "condition": "외기 12.7°C",
             "upper_label": "MJB-4 차단기", "upper_pts": [36.7, 35.5, None],
             "lower_label": "MJB-4", "lower_pts": [45.4, 38.3, None]},
            {"target": "태양광셀단자함", "voltage": "720V", "condition": "외기 12.7°C",
             "upper_label": "MJB-5 차단기", "upper_pts": [34.7, 36.3, None],
             "lower_label": "MJB-5", "lower_pts": [43.5, 36.1, None]},
            {"target": "태양광셀단자함", "voltage": "720V", "condition": "외기 12.7°C",
             "upper_label": "MJB-6 차단기", "upper_pts": [32.3, 33.3, None],
             "lower_label": "MJB-6", "lower_pts": [42.7, 36.9, None]},
        ],
        "b8_captions": [
            ["수변전실 외관", "VCB 패널", "MCCB 패널", "접지단자 점검"],
            ["축전지실 외관", "인버터 외관", "MJB 외관", "기상센서함 점검"],
        ],
    },
    "티튜브": {
        "voltage_default": "22,900V",
        "blocks": [
            {"target": "수변전실", "voltage": "22,900V", "condition": "외기 23.4°C",
             "upper_label": "CH", "upper_pts": [22.2, 22.2, 21.6],
             "lower_label": "LBS", "lower_pts": [21.3, 21.6, 21.3]},
            {"target": "수변전실", "voltage": "22,900V", "condition": "외기 23.4°C",
             "upper_label": "POWER FUSE", "upper_pts": [28.9, 29.6, 28.8],
             "lower_label": "LA", "lower_pts": [21.4, 21.6, 21.5]},
            {"target": "수변전실", "voltage": "22,900V", "condition": "외기 23.4°C",
             "upper_label": "MOF", "upper_pts": [21.7, 21.7, 21.9],
             "lower_label": "PT", "lower_pts": [33.2, 33.1, 23.3]},
            {"target": "수변전실", "voltage": "22,900V", "condition": "외기 23.4°C",
             "upper_label": "CT", "upper_pts": [21.3, 21.2, 21.1],
             "lower_label": "VCB", "lower_pts": [21.6, None, None]},
            {"target": "수변전실", "voltage": "22,900V", "condition": "외기 23.4°C",
             "upper_label": "TR", "upper_pts": [26.5, 24.1, 26],
             "lower_label": "ACB", "lower_pts": [24.7, None, None]},
            {"target": "수변전실", "voltage": "22,900V", "condition": "외기 23.4°C",
             "upper_label": "ACB 1차", "upper_pts": [32.3, 35.9, 35.1],
             "lower_label": "INVERTER", "lower_pts": [44.7, None, None]},
            {"target": "변압기,축전지", "voltage": "350/220V", "condition": "외기 23.4°C",
             "upper_label": "소내용TR", "upper_pts": [28.9, 28.5, 28.3],
             "lower_label": "축전지1~3", "lower_pts": [20.4, 20.3, 20]},
            {"target": "축전지", "voltage": "350/220V", "condition": "외기 23.4°C",
             "upper_label": "축전지4~6", "upper_pts": [19.4, 20.1, None],
             "lower_label": "축전지7~9", "lower_pts": [20, 19.8, None]},
            {"target": "태양광셀단자함", "voltage": "760V", "condition": "외기 23.4°C",
             "upper_label": "MJB-1 차단기", "upper_pts": [18.5, 18.6, None],
             "lower_label": "MJB-1", "lower_pts": [32.9, 38.5, None]},
            {"target": "태양광셀단자함", "voltage": "760V", "condition": "외기 23.4°C",
             "upper_label": "MJB-2 차단기", "upper_pts": [24.3, 24.2, None],
             "lower_label": "MJB-2", "lower_pts": [34.7, 44.3, None]},
            {"target": "태양광셀단자함", "voltage": "760V", "condition": "외기 23.4°C",
             "upper_label": "MJB-3 차단기", "upper_pts": [25.1, 24.5, None],
             "lower_label": "MJB-3", "lower_pts": [35.2, 41.6, None]},
            {"target": "태양광셀단자함", "voltage": "760V", "condition": "외기 23.4°C",
             "upper_label": "MJB-4 차단기", "upper_pts": [24.5, 24.1, None],
             "lower_label": "MJB-4", "lower_pts": [33.9, 41.4, None]},
            {"target": "태양광셀단자함", "voltage": "760V", "condition": "외기 23.4°C",
             "upper_label": "MJB-5 차단기", "upper_pts": [25.8, 25.5, None],
             "lower_label": "MJB-5", "lower_pts": [35.3, 39.6, None]},
            {"target": "태양광셀단자함", "voltage": "760V", "condition": "외기 23.4°C",
             "upper_label": "MJB-6 차단기", "upper_pts": [33.3, 32.7, None],
             "lower_label": "MJB-6", "lower_pts": [37.3, 40.6, None]},
            {"target": "태양광셀단자함", "voltage": "760V", "condition": "외기 23.4°C",
             "upper_label": "MJB-7 차단기", "upper_pts": [26.3, 26.4, None],
             "lower_label": "MJB-7", "lower_pts": [31, 30.3, None]},
            {"target": "태양광셀단자함", "voltage": "760V", "condition": "외기 23.4°C",
             "upper_label": "MJB-8 차단기", "upper_pts": [25.4, 25.9, None],
             "lower_label": "MJB-8", "lower_pts": [29.6, 29.1, None]},
        ],
        "b8_captions": [
            ["수변전실 외관", "VCB 패널", "MCCB 패널", "접지단자 점검"],
            ["축전지실 외관", "인버터 외관", "MJB 외관", "기상센서함 점검"],
        ],
    },
}


def generate_report_pdf(site_name, blocks, photos, b8_pages, out_path,
                        year_month: str = "", include_cover: bool = True,
                        b3_run: dict = None, b3_chk: dict = None, include_b3: bool = False,
                        inspection_date: str = "", p2_items: list = None, p2_results: list = None,
                        include_p2: bool = True, include_p3: bool = True, include_p4: bool = True):
    pages = []
    if include_cover:
        try: pages.append(render_cover(site_name, year_month))
        except Exception as _e: print(f"[WARN] 표지 합성 실패: {_e}")
    if include_p2:
        try: pages.append(render_p2(site_name, year_month=year_month,
                                    inspection_date=inspection_date,
                                    items=p2_items, results=p2_results))
        except Exception as _e: print(f"[WARN] 페이지2 합성 실패: {_e}")
    if include_p3:
        try: pages.append(render_p3(site_name))
        except Exception as _e: print(f"[WARN] 페이지3 합성 실패: {_e}")
    if include_p4:
        try: pages.append(render_p4(site_name))
        except Exception as _e: print(f"[WARN] 페이지4 합성 실패: {_e}")
    if include_b3:
        try: pages.append(render_b3(site_name, b3_run or {}, b3_chk or {}))
        except Exception as _e: print(f"[WARN] 붙임3 합성 실패: {_e}")
    page_num = 1
    for i, blk in enumerate(blocks):
        seed = hash(site_name) % 1000 + i * 10
        photos_for_block = photos.get(i, {}) if isinstance(photos, dict) else {}
        pages.append(render_b7(blk, page_num, photos_for_block, seed=seed))
        page_num += 1
    for items in b8_pages:
        pages.append(render_b8(items, page_num))
        page_num += 1
    if not pages:
        raise ValueError("PDF에 포함된 페이지가 없습니다. 'PDF 포함 페이지'에서 최소 1개 이상 체크해주세요.")
    pages[0].convert("RGB").save(
        out_path, "PDF", resolution=200.0,
        save_all=True,
        append_images=[p.convert("RGB") for p in pages[1:]],
    )
    return out_path
