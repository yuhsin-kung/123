@echo off
setlocal
cd /d D:\trade-rag\src
set OLLAMA_MODELS=D:\ollama\models
netstat -ano | findstr ":7860" >nul 2>&1
if %ERRORLEVEL%==0 exit /b 0
if not exist "D:\trade-rag\.venv\Scripts\python.exe" exit /b 1
start "trade-rag" /min "D:\trade-rag\.venv\Scripts\python.exe" -u chat_ui.py
exit /b 0
