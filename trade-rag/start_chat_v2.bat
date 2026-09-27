@echo off
REM trade-rag v2（全功能助理：交易＋學校＋一般聊天）— 與正式版 7860 並行，跑在 7861
cd /d D:\trade-rag\src
set OLLAMA_MODELS=D:\ollama\models
set TRADE_RAG_PORT=7861
echo Open browser: http://127.0.0.1:7861   (v2)
D:\trade-rag\.venv\Scripts\python.exe chat_ui_v2.py
pause
