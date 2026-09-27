@echo off
REM 啟動開發伺服器：http://127.0.0.1:8000/ （按 Ctrl+C 停止）
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
.venv\Scripts\python manage.py runserver 127.0.0.1:8000
