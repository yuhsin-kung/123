@echo off
REM 行事曆（ICS）＋ 行事曆 PDF ＋ 學士班選課註冊時間表：建議每週 1 次。約 4–6 個請求。
REM PDF 解析需要 poppler 的 pdftotext（沒有的話 ICS 仍會更新，PDF 兩項會記錄錯誤）
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
if not exist logs mkdir logs
.venv\Scripts\python manage.py crawl_events --only calendar >> logs\crawl_calendar.log 2>&1
