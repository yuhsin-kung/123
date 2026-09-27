@echo off
setlocal
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "DST=%STARTUP%\TW_Login_Watcher_And_RAG.bat"
set "WATCH=C:\Users\AUSER\Desktop\trade\snr_backtest\start_paper_watcher.bat"
set "RAG=D:\trade-rag\start_chat_silent.bat"
set "RAG2=D:\trade-rag\start_chat_v2_silent.bat"
if not exist "%WATCH%" (echo ERROR missing watcher & pause & exit /b 1)
if not exist "%RAG%" (echo ERROR missing RAG silent bat & pause & exit /b 1)
if not exist "%RAG2%" (echo ERROR missing RAG v2 silent bat & pause & exit /b 1)
(
echo @echo off
echo REM Login autostart: paper watcher + trade-rag v1 and v2
echo call "%WATCH%"
echo call "%RAG%"
echo call "%RAG2%"
) > "%DST%"
echo Installed: %DST%
echo On next login: watcher + RAG will start.
echo Ollama already in Startup.
echo.
echo Starting RAG once now...
call "%RAG%"
echo Done.
pause