@echo off
cd /d "%~dp0"
echo 서버를 시작합니다...
echo 브라우저에서 http://localhost:5000 으로 접속하세요.
echo 종료하려면 이 창을 닫으세요.
echo.
start http://localhost:5000
python app.py
pause
