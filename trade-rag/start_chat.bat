@echo off
cd /d D:\trade-rag\src
set OLLAMA_MODELS=D:\ollama\models
echo Open browser: http://127.0.0.1:7860
D:\trade-rag\.venv\Scripts\python.exe chat_ui.py
pause
