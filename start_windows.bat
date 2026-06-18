@echo off
REM 윈도우에서 더블클릭하면 화면(웹) 방식이 켜집니다.
cd /d "%~dp0"
echo 필요한 라이브러리를 확인/설치합니다...
pip install -r requirements.txt
echo.
echo 브라우저에서 http://127.0.0.1:5000 으로 접속하세요.
python web_app.py
pause
