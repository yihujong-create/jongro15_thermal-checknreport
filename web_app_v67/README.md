# 열화상 분기점검 보고서 자동 생성 웹앱

종로전기㈜ 태양광발전 사업부 사내용 — KCC 부산 3개 사이트(조달청 청사 / 비축기지 / 티튜브)의 분기점검 보고서를 브라우저에서 자동 생성합니다.

## 빠른 시작 (Windows)

1. Python 3.10+ 설치 ([python.org](https://www.python.org/downloads/))
2. `run.bat` 더블클릭
3. 브라우저에서 자동으로 열리는 [http://localhost:5000](http://localhost:5000) 접속

처음 실행 시 가상환경 생성과 의존성 설치 때문에 1~2분 소요됩니다.

## 빠른 시작 (Mac/Linux)

```bash
cd web_app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

## 기능

- **사이트 선택** — 조달청 청사 / 비축기지 / 티튜브 (엑셀 원본 기준 4 / 14 / 16 블록)
- **측정값 입력** — 엑셀의 실측값이 기본값으로 채워져 있으며 수정 가능
- **사진 업로드** — 블록별 실화상/열화상 + 붙임8 점검사진 8장
- **자동 placeholder** — 사진 미업로드 시 측정값에 맞춘 가짜 열화상 자동 생성
- **종합의견 자동 분류** — 5℃ 이하 정상 / 5~10℃ 요주의 / 10℃ 이상 이상
- **PDF 다운로드** — 사내 양식(붙임7 + 붙임8) 그대로 출력

## 파일 구조

```
web_app/
├── app.py                  # Flask 진입점
├── report_engine.py        # PDF 생성 엔진 (Pillow)
├── requirements.txt
├── run.bat                 # Windows 실행 스크립트
├── README.md
├── templates/
│   ├── index.html          # 사이트 선택 페이지
│   └── site_form.html      # 측정값/사진 입력 폼
├── static/
│   └── style.css
├── uploads/                # 업로드 사진 임시 저장
└── reports/                # 생성된 PDF 저장
```

## 출력 PDF 페이지 수

| 사이트 | B7 페이지 | B8 페이지 | 합계 |
|---|---|---|---|
| 조달청 청사 | 4 | 2 | 6p |
| 비축기지 | 14 | 2 | 16p |
| 티튜브 | 16 | 2 | 18p |

## 사내 IT 환경에서 공유 서버로 배포

만약 한 대의 PC에 설치하고 사내 망에서 여러 사람이 접속하게 하려면:

1. `app.py`의 `app.run(host="0.0.0.0", port=5000)` 그대로 사용
2. 방화벽에서 5000 포트 인바운드 허용
3. 다른 PC에서 `http://<서버PC_IP>:5000` 으로 접속

## 한글 폰트

PDF에 한글이 깨져 보이면:
- Windows: 시스템에 기본 설치된 맑은 고딕(`malgun.ttf`)을 자동 사용
- Linux: `apt install fonts-droid-fallback` 또는 NotoSansKR 설치
- 폰트 경로 추가는 [report_engine.py](report_engine.py)의 `_FONT_DIRS_KR` 리스트 확인

## 문제 해결

| 증상 | 원인/해결 |
|---|---|
| `run.bat` 실행 시 "Python이 없습니다" | Python 설치 후 "Add Python to PATH" 옵션 체크 |
| 한글이 □로 표시 | OS에 한글 폰트 설치 |
| 사진 업로드 실패 | 파일 크기 100MB 이하인지 확인 |
| 포트 충돌 | `app.py`의 port=5000을 다른 번호로 변경 |

## 라이선스

종로전기㈜ 사내용. 외부 배포 금지.
