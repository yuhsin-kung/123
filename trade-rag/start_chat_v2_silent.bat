@echo off
REM 背景啟動 v2（7861）；已在跑就不重複啟動。輸出寫到 D:\trade-rag\logs\v2_server.log
setlocal
cd /d D:\trade-rag\src
set OLLAMA_MODELS=D:\ollama\models
set TRADE_RAG_PORT=7861
set PYTHONIOENCODING=utf-8
netstat -ano | findstr "127.0.0.1:7861" | findstr LISTENING >nul 2>&1
if %ERRORLEVEL%==0 exit /b 0
if not exist "D:\trade-rag\logs" mkdir "D:\trade-rag\logs"
start "trade-rag-v2" /min cmd /c ""D:\trade-rag\.venv\Scripts\python.exe" -u chat_ui_v2.py >> "D:\trade-rag\logs\v2_server.log" 2>&1"
exit /b 0
