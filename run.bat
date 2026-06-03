@echo off
chcp 65001 > nul
echo ============================================================
echo  열화상 분기점검 보고서 자동 생성 웹앱
echo ============================================================
echo.

REM Python 설치 확인
where python >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo https://www.python.org/downloads/ 에서 Python 3.10+ 를 설치하세요.
    pause
    exit /b 1
)

REM 가상환경 (선택)
if not exist venv (
    echo [1/3] 가상환경 생성 중...
    python -m venv venv
)
call venv\Scripts\activate.bat

REM 의존성 설치
echo [2/3] 의존성 설치 중...
pip install -q -r requirements.txt

REM 서버 실행
echo [3/3] 서버 시작...
echo.
echo 브라우저에서 다음 주소로 접속:
echo   http://localhost:5000
echo.
echo 종료하려면 Ctrl+C 또는 이 창을 닫으세요.
echo ============================================================
python app.py
pause
