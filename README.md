# 東吳學生入口＋阿斯拉

三個可以分開跑的專案放在同一個倉庫。給沒看過這台電腦的人：先看這份，不要從子資料夾的舊說明開始。

| 資料夾 | 是什麼 | 不跑它會怎樣 |
|---|---|---|
| `scu-portal` | 瀏覽器裡的學生入口。課表、選課、成績、行事曆、右下角的阿斯拉 | 沒有畫面 |
| `scu-backend` | 爬學校公開網頁，存進資料庫 | 入口站仍可開。它讀的是已經產生好的 `scu-portal/js/data-courses.js`，不是每次都連這個資料庫 |
| `trade-rag` | 本機語言模型。阿斯拉答不了、又屬於東吳或學生事務的問題，會來問它 | 入口站還在。阿斯拉只靠關鍵字回答，來源會寫「語言模型未連線」 |

對話模型是 Ollama 的 `qwen2.5:3b`。找文件用的是 `paraphrase-multilingual-MiniLM-L12-v2`。這兩個都沒有換成別的。

## 只想看入口站

用 Chrome 或 Edge 打開 `scu-portal/index.html`。不用安裝、不用建置。

- 桌機：左邊功能選單，中間常用功能和課表，右邊行事曆。
- 手機寬度：底部五個分頁。課表改成一天一天看。
- 右下角紅色的「阿」可以拖。拖完的位置記在這台瀏覽器。視窗只變高（網址列伸縮）時不會把它推走。
- 現在時間跟這台電腦走。網址加 `?date=2026-09-28&time=10:30` 可以暫時指定。
- 選課車、常用功能次數存在瀏覽器的 localStorage。`#/settings` 可以重設。

課程是 115 學年度第 1 學期爬來的公開課表，寫在 `js/data-courses.js`。示範學生是王小明，資料科學系三年級 B 班，課表裡有他的選課（含星期五第 5–6 節的互動科技）。入口站上的行事曆和成績仍是示範數字，不是爬蟲那份。

阿斯拉先用關鍵字查站內資料，再決定要不要問語言模型。

- 「星期三我有什麼課」「這學期平日有哪幾天被放掉」這類，直接用站內課表或行事曆回答。
- 和東吳、學生事務無關的問題（例如算術、教數學）會拒絕，不會亂答。
- 站內沒有、但屬於學校或學生問題時，才呼叫 `http://127.0.0.1:7861/api/chat`。那個程式沒開，就會顯示語言模型未連線，並留下關鍵字能給的答案。

## 要讓阿斯拉連上語言模型

另外需要 [Ollama](https://ollama.com/)。裝好後：

```bat
ollama pull qwen2.5:3b
```

然後在 `trade-rag`：

```bat
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd src
python build_store.py
python chat_ui_v2.py
```

瀏覽器打開 <http://127.0.0.1:7861>。這是深色的對話頁，和入口站是兩個畫面。入口站的阿斯拉會把問句送到這個位址。

`build_store.py` 會產生 `indexes/`。這個資料夾沒有進 Git，因為可以重建。沒有索引時，文件檢索沒有東西可找；課表和行事曆若走資料庫查詢，則還要先把 `scu-backend` 的資料庫準備好。

倉庫裡的 `start_chat_v2.bat` 寫死了 `D:\trade-rag`。換一台電腦請改 bat，或直接用上面的 `python chat_ui_v2.py`。

Ollama 有在跑，不代表 7861 有在跑。入口站只認 7861。這個 Python 程式答完一題不會自己關。超過約 5 分鐘沒人問，模型會從記憶體卸掉，下一題會慢，但連接還在。

## 要更新爬來的學校資料

在 `scu-backend`：

```bat
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py import_timetable_db --semester 115-1
python manage.py import_events_db
python manage.py setup_demo
python manage.py runserver
```

- 後端：<http://127.0.0.1:8000/>
- 管理畫面：<http://127.0.0.1:8000/admin/>
- 示範帳號：`demo`／`demo1234`

`import_*` 讀的是 `data/` 裡已經爬好的快照，不用先連網。想重新抓公開網頁再用：

```bat
python manage.py crawl_timetable
python manage.py crawl_events
python manage.py crawl_announcements
```

行事曆 PDF 若要解析，還需要系統裡的 poppler（`pdftotext`）。沒有它，Google 行事曆和公告仍可抓。

Git 沒有放 `db.sqlite3` 和 `.venv`。`data/` 裡的課表、行事曆快照有放進來，所以上面的 import 做完就有資料。

## 三份資料不要混在一起想

- 入口站課表：`scu-portal/js/data-courses.js`
- 入口站行事曆、成績：`js/data-calendar.js`、`js/data-grades.js`（示範）
- 阿斯拉的學校問答：`scu-backend` 資料庫裡爬來的行事曆和課表
- 交易規則問答：`trade-rag/data/rules/`，跟東吳無關

所以「入口站說的放假」和「深色對話頁說的放假」可能不是同一份。
