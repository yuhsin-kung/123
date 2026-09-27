@echo off
set "DST=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\TW_Login_Watcher_And_RAG.bat"
if exist "%DST%" del /F /Q "%DST%"
schtasks /Delete /F /TN "TW_Paper_OnLogon" >nul 2>&1
schtasks /Delete /F /TN "TW_TradeRag_OnLogon" >nul 2>&1
echo Removed login autostart shortcut (and any leftover OnLogon tasks).
pause