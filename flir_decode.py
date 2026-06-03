# -*- coding: utf-8 -*-
"""
FLIR R-JPEG 디코더.
APP1 segments에서 FFF 데이터를 재구성 → raw thermal PNG/TIFF 추출 →
Planck constants로 픽셀별 온도 변환.
"""
import struct
import math
import io
from typing import Optional, Dict, Tuple
from PIL import Image


def _read_flir_app1_segments(data: bytes) -> bytes:
    """모든 FLIR APP1 segments를 sequence 순으로 합쳐 FFF 데이터 반환."""
    pos = 0
    payloads = []
    while True:
        p = data.find(b'\xFF\xE1', pos)
        if p < 0:
            break
        seg_len = struct.unpack('>H', data[p+2:p+4])[0]
        header = data[p+4:p+12]
        if header.startswith(b'FLIR\x00'):
            seq = data[p+10]
            payload = data[p+12:p+2+seg_len]
            payloads.append((seq, payload))
        pos = p + 2 + seg_len
    payloads.sort(key=lambda x: x[0])
    return b''.join(p[1] for p in payloads)


def _parse_chunks(fff: bytes) -> Dict[int, Tuple[int, int]]:
    """FFF dir entries 파싱 → {type: (offset, length)}."""
    if not fff.startswith(b'FFF\x00'):
        return {}
    dir_off = struct.unpack('>I', fff[0x18:0x1C])[0]
    dir_cnt = struct.unpack('>I', fff[0x1C:0x20])[0]
    chunks = {}
    for i in range(dir_cnt):
        e = fff[dir_off + i*32 : dir_off + (i+1)*32]
        if len(e) < 20:
            break
        type_, sub, ver, idx, off, length = struct.unpack('>HHIIII', e[:20])
        if length > 0:
            chunks[type_] = (off, length)
    return chunks


def _read_calibration(cal: bytes) -> dict:
    """Type 0x0020 청크에서 Planck constants + 환경 파라미터 추출.
    PlanckO는 ExifTool 표준 위치 0x308 (int32 LE)에서 읽음."""
    def f(off):
        return struct.unpack('<f', cal[off:off+4])[0] if off+4 <= len(cal) else None
    def i(off):
        return struct.unpack('<i', cal[off:off+4])[0] if off+4 <= len(cal) else None
    
    # PlanckO 표준 위치 (ExifTool FlirRecord 0x40 BasicData의 0x308)
    planck_o = i(0x308)
    # 합리적 범위 체크: PlanckO는 보통 -10000 ~ 0 사이 정수
    if planck_o is None or planck_o < -20000 or planck_o > 5000:
        planck_o = 0
    
    return {
        'Emissivity': f(0x20),
        'ObjectDistance': f(0x24),
        'ReflectedTemp': f(0x28),       # in K
        'AtmosphericTemp': f(0x30),     # in K
        'PlanckR1': f(0x58),
        'PlanckB': f(0x5C),
        'PlanckF': f(0x60),
        'PlanckO': planck_o,            # 0x308 (int32) — 표준 위치
        'PlanckR2': f(0x74),
    }


def _read_raw_thermal(raw_chunk: bytes):
    """RawData 청크에서 thermal 이미지 디코딩.
    Returns: numpy.ndarray (uint16, byteswapped if needed) of shape (H, W)
    """
    import numpy as np
    png_start = raw_chunk.find(b'\x89PNG')
    tif_start = raw_chunk.find(b'II*\x00')
    img = None
    if png_start >= 0:
        img = Image.open(io.BytesIO(raw_chunk[png_start:]))
    elif tif_start >= 0:
        img = Image.open(io.BytesIO(raw_chunk[tif_start:]))
    if img is None:
        return None
    arr = np.array(img)
    # FLIR raw PNG는 big-endian으로 인코딩되어 있어 byteswap 필요
    # (heuristic: 평균이 30000~60000이면 byteswap, 그 외 그대로)
    if arr.dtype == np.uint16 and arr.mean() > 25000:
        arr = arr.byteswap()
    return arr


def _raw_to_temp_celsius(raw_val: float, cal: dict) -> float:
    """Planck 공식으로 raw pixel value → temperature (°C)."""
    R1 = cal['PlanckR1']
    R2 = cal['PlanckR2']
    B = cal['PlanckB']
    F = cal['PlanckF']
    O = cal.get('PlanckO', 0) or 0
    
    # 표준 FLIR Planck 공식:
    # T(K) = B / log(R1 / (R2 * (raw + O)) + F)
    try:
        denom = R2 * (raw_val + O)
        if denom <= 0:
            return float('nan')
        ratio = R1 / denom + F
        if ratio <= 0:
            return float('nan')
        T_K = B / math.log(ratio)
        return T_K - 273.15
    except Exception:
        return float('nan')


def decode_flir(jpeg_path: str) -> Optional[dict]:
    """
    R-JPEG 파일 분석 → 디코딩 결과 반환.
    
    Returns: {
        'success': bool,
        'width': int, 'height': int,
        'calibration': {Planck constants...},
        'raw_image': PIL.Image (mode='I;16' or 'I' grayscale),
        'temp_min': float, 'temp_max': float, 'temp_mean': float,
    } or None
    """
    with open(jpeg_path, 'rb') as f:
        data = f.read()
    
    fff = _read_flir_app1_segments(data)
    if not fff or len(fff) < 64:
        return None
    
    chunks = _parse_chunks(fff)
    
    # Calibration
    cal_off_len = chunks.get(0x0020)
    if not cal_off_len:
        return None
    cal_data = fff[cal_off_len[0] : cal_off_len[0] + cal_off_len[1]]
    cal = _read_calibration(cal_data)
    
    # RawData
    raw_off_len = chunks.get(0x0001)
    if not raw_off_len:
        return None
    raw_chunk = fff[raw_off_len[0] : raw_off_len[0] + raw_off_len[1]]
    raw_arr = _read_raw_thermal(raw_chunk)
    if raw_arr is None:
        return None
    
    h, w = raw_arr.shape
    
    # PlanckO 합리성 검증 — 적용 결과가 -40~+150°C 안이어야 정상
    try:
        import numpy as _np
        flat = raw_arr.flatten()
        # 샘플 100개로 빠르게 검증
        sample = flat[::max(1, len(flat)//100)]
        temps_with_O = [_raw_to_temp_celsius(int(p), cal) for p in sample]
        valid_with_O = [t for t in temps_with_O if t is not None and not math.isnan(t)]
        mean_with_O = sum(valid_with_O)/len(valid_with_O) if valid_with_O else None
        # 합리적 범위 밖이면 PlanckO=0으로 fallback
        if mean_with_O is None or mean_with_O < -30 or mean_with_O > 150:
            cal_bak = dict(cal); cal_bak['PlanckO'] = 0
            temps_O0 = [_raw_to_temp_celsius(int(p), cal_bak) for p in sample]
            valid_O0 = [t for t in temps_O0 if t is not None and not math.isnan(t)]
            mean_O0 = sum(valid_O0)/len(valid_O0) if valid_O0 else None
            # 0으로도 결과가 합리적이면 0 사용
            if mean_O0 is not None and -30 < mean_O0 < 150:
                print(f"[INFO] PlanckO={cal['PlanckO']} 비합리적 결과({mean_with_O:.1f}°C) → 0으로 fallback")
                cal['PlanckO'] = 0
    except Exception as _verr:
        print(f"[WARN] PlanckO 검증 실패: {_verr}")
    
    # 전체 픽셀 통계 (sampling)
    flat = raw_arr.flatten()
    sample = flat[::max(1, len(flat)//1000)]
    temps = [_raw_to_temp_celsius(int(p), cal) for p in sample]
    temps = [t for t in temps if not math.isnan(t)]
    
    return {
        'success': True,
        'width': int(w),
        'height': int(h),
        'calibration': cal,
        'raw_array': raw_arr,
        'temp_min': float(min(temps)) if temps else None,
        'temp_max': float(max(temps)) if temps else None,
        'temp_mean': float(sum(temps)/len(temps)) if temps else None,
    }


def get_temp_at_pixel(decoded: dict, x: int, y: int) -> Optional[float]:
    """디코딩된 R-JPEG 결과의 raw 이미지에서 (x, y) 좌표의 온도 (°C)."""
    arr = decoded['raw_array']
    h, w = arr.shape
    if not (0 <= x < w and 0 <= y < h):
        return None
    raw_val = int(arr[y, x])
    t = _raw_to_temp_celsius(raw_val, decoded['calibration'])
    return None if math.isnan(t) else round(t, 1)


def get_temp_in_box(decoded: dict, x1: int, y1: int, x2: int, y2: int) -> dict:
    """박스 영역의 max/min/avg 온도 (°C) + max/min 위치 좌표."""
    arr = decoded['raw_array']
    h, w = arr.shape
    x1, x2 = max(0, min(x1, x2)), min(w, max(x1, x2))
    y1, y2 = max(0, min(y1, y2)), min(h, max(y1, y2))
    
    region = arr[y1:y2, x1:x2]
    if region.size == 0:
        return {'max': None, 'min': None, 'avg': None,
                'max_x': None, 'max_y': None, 'min_x': None, 'min_y': None}
    
    # 픽셀별 온도 계산 (numpy 2D)
    import numpy as np
    flat = region.flatten()
    temps = np.array([_raw_to_temp_celsius(int(p), decoded['calibration']) for p in flat])
    # NaN 제거 후 통계
    valid_mask = ~np.isnan(temps)
    if not valid_mask.any():
        return {'max': None, 'min': None, 'avg': None,
                'max_x': None, 'max_y': None, 'min_x': None, 'min_y': None}
    
    temps_2d = temps.reshape(region.shape)
    # max/min 위치 (region 내 인덱스 → 전체 좌표 변환)
    max_idx = np.nanargmax(temps_2d)
    min_idx = np.nanargmin(temps_2d)
    max_y_rel, max_x_rel = np.unravel_index(max_idx, temps_2d.shape)
    min_y_rel, min_x_rel = np.unravel_index(min_idx, temps_2d.shape)
    
    valid_temps = temps[valid_mask]
    return {
        'max': round(float(valid_temps.max()), 1),
        'min': round(float(valid_temps.min()), 1),
        'avg': round(float(valid_temps.mean()), 1),
        'max_x': int(x1 + max_x_rel),
        'max_y': int(y1 + max_y_rel),
        'min_x': int(x1 + min_x_rel),
        'min_y': int(y1 + min_y_rel),
    }



def extract_embedded_visible(jpeg_path):
    """
    FLIR R-JPEG에서 embedded visible image(실화상 JPEG) bytes를 추출.

    FFF chunk type 0x000E = EmbeddedImage:
      - 32 byte 헤더 (uint16 type, uint16 width, uint16 height, ...)
      - 그 다음 표준 JPEG 데이터 (FFD8FF로 시작)
    
    FLIR ONE: 1440×1080 visible (별도 가시광 카메라)
    FLIR E5 Pro: 640×480 visible

    Returns: visible image JPEG bytes, 추출 불가 시 None
    """
    try:
        with open(jpeg_path, 'rb') as f:
            data = f.read()
    except Exception:
        return None

    fff = _read_flir_app1_segments(data)
    if not fff or len(fff) < 64:
        return None

    chunks = _parse_chunks(fff)

    # FLIR 표준: type 0x000E = EmbeddedImage
    for chunk_type in (0x000E, 0x000D):
        emb = chunks.get(chunk_type)
        if not emb:
            continue
        off, length = emb
        chunk_data = fff[off:off + length]
        # 32 byte 헤더 건너뛰기 후 JPEG 찾기
        j_start = chunk_data.find(b'\xFF\xD8\xFF')
        if j_start >= 0:
            j_end = chunk_data.rfind(b'\xFF\xD9')
            if j_end > j_start:
                return chunk_data[j_start:j_end + 2]
            return chunk_data[j_start:]

    # 폴백: FFF 전체에서 JPEG 시그니처 스캔 (20KB 초과만)
    j_start = fff.find(b'\xFF\xD8\xFF')
    while j_start >= 0:
        j_end = fff.find(b'\xFF\xD9', j_start + 2)
        if j_end > j_start:
            candidate = fff[j_start:j_end + 2]
            if len(candidate) > 20000:
                return candidate
        j_start = fff.find(b'\xFF\xD8\xFF', j_start + 2)

    return None


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else \
        "/sessions/funny-confident-archimedes/mnt/KCC보고서/열화상 및 사진/조달청/FLIR0297.jpg"
    
    print(f"--- {path} ---")
    result = decode_flir(path)
    if not result:
        print("디코딩 실패")
        sys.exit(1)
    
    print(f"Raw thermal: {result['width']} x {result['height']}")
    print(f"Calibration: {result['calibration']}")
    print(f"Temperature range: {result['temp_min']:.1f}°C ~ {result['temp_max']:.1f}°C (avg {result['temp_mean']:.1f}°C)")
    
    # 가운데 픽셀 온도
    cx, cy = result['width']//2, result['height']//2
    t_center = get_temp_at_pixel(result, cx, cy)
    print(f"Center ({cx},{cy}) temp: {t_center:.1f}°C")
    
    # 9개 sample point
    print("\n9-point grid sample:")
    for dy in [0.25, 0.5, 0.75]:
        row = []
        for dx in [0.25, 0.5, 0.75]:
            x = int(result['width'] * dx)
            y = int(result['height'] * dy)
            t = get_temp_at_pixel(result, x, y)
            row.append(f"{t:5.1f}°C")
        print("  " + "  ".join(row))
    
    # 박스 (중앙 1/3)
    bx = result['width'] // 3
    by = result['height'] // 3
    box = get_temp_in_box(result, bx, by, 2*bx, 2*by)
    print(f"\nBox center 1/3: max={box['max']}°C, min={box['min']}°C, avg={box['avg']}°C")
