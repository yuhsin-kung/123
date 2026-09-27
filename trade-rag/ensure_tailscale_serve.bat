@echo off
set "TS=C:\Program Files\Tailscale\tailscale.exe"
if not exist "%TS%" exit /b 0
"%TS%" serve --bg --yes --http=7860 http://127.0.0.1:7860 >nul 2>&1
"%TS%" serve --bg --yes --http=8501 http://127.0.0.1:8501 >nul 2>&1
exit /b 0
