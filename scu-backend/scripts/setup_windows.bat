@echo off
REM 第一次安裝（Windows）：建立 .venv、安裝套件、建資料表、匯入資料、建立示範帳號
REM 用法：在 scu-backend 資料夾按兩下，或在 cmd 執行 scripts\setup_windows.bat
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv || python -m venv .venv
)
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py import_timetable_db --semester 115-1
.venv\Scripts\python manage.py import_events_db
.venv\Scripts\python manage.py setup_demo
echo.
echo 完成！接著執行 scripts\run_server.bat，然後打開 http://127.0.0.1:8000/
echo 要進 /admin/ 請先建立管理員：.venv\Scripts\python manage.py createsuperuser
pause
