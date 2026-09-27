@echo off
REM 校園公告：建議每天 2 次（07:30、17:30）。約 2–5 個請求。
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
if not exist logs mkdir logs
.venv\Scripts\python manage.py crawl_announcements --pages 2 >> logs\crawl_news.log 2>&1
