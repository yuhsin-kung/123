@echo off
REM 全校課表：一學期 1 次（初選前），可選擇加退選前再 1 次。約 520 個請求、10–15 分鐘（每次請求間隔 ≥1.2 秒）。
REM 用法：scripts\crawl_timetable.bat 115-2
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
if "%~1"=="" (echo 請給學期，例如 scripts\crawl_timetable.bat 115-2 & exit /b 1)
if not exist logs mkdir logs
.venv\Scripts\python manage.py crawl_timetable --semester %1 >> logs\crawl_timetable.log 2>&1
REM 限修條件（選課限制查詢）：只抓示範學生相關系所，約 500–600 個請求
.venv\Scripts\python manage.py crawl_rules --semester %1 --dept 資料科學系 --dept 通識 --dept 體育 --dept 全校選修 >> logs\crawl_timetable.log 2>&1
