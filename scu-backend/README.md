# scu-backend：東吳學生新入口的 Django 後端

黑客松示範用的後端。把兩支爬蟲（`scu-scraper` 全校課表、`scu-events` 行事曆與公告）抓到的**學校公開資料**
放進 Django 資料庫，並提供 JSON API。前端網站 `scu-portal-demo` 之後就可以改用 `fetch('/api/...')` 取資料，不必再讀產生出來的 `real-*.js`。

- 示範學生：**王小明**，學士班 資料科學系 三年級 B 班（帳號 `demo`／密碼 `demo1234`）
- 資料：115-1 全校課程 3,432 門、515 個班級、限修條件、115 學年行事曆、校園公告
- **示範資料（不是真的）**：已選人數（模擬）、學分上下限 16–25、示範學生本人、「現在時間」（預設 2026-09-30 10:30）

---

## 1. 快速開始（Windows）

在 `scu-backend` 資料夾打開「命令提示字元」（cmd）：

```bat
:: 1) 建立虛擬環境（只做一次）。.venv 是這個專案自己的 Python 套件空間，不會影響其他專案
py -3 -m venv .venv
.venv\Scripts\activate

:: 2) 安裝套件
pip install -r requirements.txt

:: 3) 建立資料表（依照各 app 的 migrations/）
python manage.py migrate

:: 4) 匯入資料（不連網，讀 data\ 裡爬蟲產生的 SQLite 快照）
python manage.py import_timetable_db --semester 115-1
python manage.py import_events_db
python manage.py setup_demo            :: 建立 demo 帳號＋資科三B 初始課表

:: 5) 建立管理員帳號（登入 /admin/ 用，帳號密碼自己取）
python manage.py createsuperuser

:: 6) 啟動
python manage.py runserver
```

打開 <http://127.0.0.1:8000/>（API 列表）、<http://127.0.0.1:8000/admin/>（資料庫管理）。按 `Ctrl+C` 停止。
懶得打指令：`scripts\setup_windows.bat` 做完 1–4，`scripts\run_server.bat` 啟動。

> 如果 cmd 印中文出現亂碼或 `UnicodeEncodeError`，先執行 `set PYTHONUTF8=1`（bat 檔裡已經加了）。

測試：`python manage.py test`（30 個測試，約 1 秒）。

---

## 2. 專案結構

```
scu-backend/
├─ manage.py                 Django 的指令入口（runserver、migrate、test、自訂指令都從這裡跑）
├─ requirements.txt          需要的套件（Django 5.2 LTS、requests、beautifulsoup4、lxml、certifi）
├─ config/                   「專案」設定（不是 app）
│  ├─ settings.py            設定：INSTALLED_APPS、SQLite、Asia/Taipei、zh-hant、SCU_* 自訂設定
│  ├─ urls.py                網址總表：/admin/、/api/…、/（前端）
│  ├─ api.py                 JSON 回應小工具 api_ok / api_error / read_json
│  └─ wsgi.py / asgi.py      上線時給網頁伺服器用（開發不用管）
├─ timetable/                課程 app
│  ├─ models.py              ScrapeRun、Program、Department、SchoolClass、Course、ClassCourse、CourseSession、CourseRule、CourseRestriction
│  ├─ catalog.py             把資料庫課程整理成前端格式＋記憶體快取；real-*.js 相容格式（bundle）
│  ├─ eligibility.py         限修檢查 can_take()（= 前端 core.js 的 S.canTake）
│  ├─ views.py / urls.py     /api/programs、/api/departments、/api/classes、/api/courses …
│  ├─ admin.py               admin 註冊（搜尋、篩選、課程內嵌上課時段）
│  ├─ scu/class40.py         scu-scraper/scrape_class40.py 的快照（抓取＋解析）
│  ├─ management/commands/   import_timetable_db、crawl_timetable、crawl_rules
│  └─ tests.py
├─ events/                   全校事務 app
│  ├─ models.py              Event（行事曆／選課時程）、Announcement（公告）、CrawlLog
│  ├─ services.py            轉成前端 real-events.js 格式（移植 export_frontend.py）
│  ├─ views.py / urls.py     /api/events、/api/news、/api/bundle/events
│  ├─ crawler/               scu-events 爬蟲快照（scrape_events.py、scu_common.py、certs/）
│  └─ management/commands/   import_events_db、crawl_events、crawl_announcements
├─ accounts/                 學生帳號 app
│  ├─ models.py              StudentProfile（一對一掛在 Django User 上）
│  ├─ services.py            current_user()：登入者，或示範模式自動當 demo
│  ├─ views.py / urls.py     /api/profile、/api/login、/api/logout
│  ├─ templates/registration/login.html   /accounts/login/ 登入頁
│  └─ management/commands/setup_demo.py   建立王小明＋初始課表
├─ enrollment/               選課 app（本專案的重點）
│  ├─ models.py              Enrollment（我的課表）、CartItem（選課車）、Submission（送出紀錄）、DemoClock（示範時鐘）
│  ├─ clock.py               系統的「現在」：admin 示範時鐘 > settings.SCU_DEMO_NOW > 真實時間
│  ├─ windows.py             從行事曆推算選課時段（初選、加退選①–④、即時退選…），判斷能不能加／退選
│  ├─ checks.py              衝堂、學分 16–25、額滿（模擬）、限修
│  ├─ seats.py               模擬已選人數
│  ├─ services.py            選課車、送出、初始課表
│  ├─ views.py / urls.py     /api/selection/window、/api/cart、/api/cart/submit、/api/me/timetable
│  └─ tests.py               選課檢查＋時段鎖定測試
├─ portal/                   前端網站 app：/ 回傳 frontend/index.html，/js/…、/css/… 回傳檔案
│  └─ management/commands/sync_frontend.py   把 scu-portal-demo 複製一份進 frontend/
├─ frontend/index.html       目前是佔位頁（列出 API 連結）
├─ data/                     爬蟲 SQLite 快照：scu_timetable.db、scu_events.db（匯入指令的預設來源）
└─ scripts/                  Windows 批次檔：安裝、啟動、排程用的爬蟲
```

`db.sqlite3` 是 Django 自己的資料庫（migrate 後產生）；`data/*.db` 只是匯入來源。

### 為什麼分成這幾個 app？
Django 的 app ＝「一組相關的 model＋view＋url＋admin」。依照「資料是誰的、多久變一次」切：

| app | 資料 | 更新頻率 |
|---|---|---|
| timetable | 課程、班級課表、限修 | 一學期 1–2 次（爬蟲或匯入） |
| events | 行事曆、選課時程、公告 | 每週／每天 |
| accounts | 學生身分 | 登入時 |
| enrollment | 我的課表、選課車 | 使用者每次操作 |
| portal | 前端檔案 | 前端改版時 |

---

## 3. 一個 request 的旅程：URL → view → model → JSON

以 `GET /api/courses?dept=資料科學系&grade=3` 為例：

1. **URL**：`config/urls.py` 有 `path("api/", include("timetable.urls"))`，`timetable/urls.py` 有 `path("courses", views.courses_api)` → 交給 `courses_api`。
2. **View**：`timetable/views.py` 的 `courses_api(request)` 從 `request.GET` 讀 `dept`、`grade`；用 `accounts.services.current_user()` 知道是誰（限修判斷要用）。
3. **Model**：`timetable/catalog.py` 的 `get_catalog()` 用 ORM 查 `Course`、`CourseSession`、`ClassCourse`、`CourseRestriction`（例如 `Course.objects.filter(semester=...)`），整理好放記憶體快取。
4. **JSON**：每門課經過 `Catalog.course_json()` 變成 dict，`config/api.py` 的 `api_ok()` 用 `JsonResponse` 回傳（`ensure_ascii=False` 讓中文直接顯示）。

寫入的例子 `POST /api/cart`：`enrollment/views.py cart_api` → `window_status()`（查 `events.Event`）→ 時段不對回 403 → 否則 `CartItem.objects.update_or_create(...)` 寫入資料庫 → 回傳選課車與檢查結果。

---

## 4. API 一覽

全部回傳 JSON（UTF-8）。沒登入時預設當作示範學生 demo（`SCU_DEMO_AUTOLOGIN`）。

| 方法 | 網址 | 說明 | 對應前端 data-source.js |
|---|---|---|---|
| GET | `/api/profile` | 登入學生（同 profile.js 欄位＋college、classLabel）；會種 csrftoken cookie | `getProfile()` |
| GET | `/api/periods` | 節次 1–4、E、5–9、A–D 與時間 | `getPeriods()` |
| GET | `/api/programs` | 學制 | `getPrograms()` |
| GET | `/api/departments?program=` | 系所（只列有班級的） | `getDeptLabels()` |
| GET | `/api/classes?program=&dept=&grade=` | 班級 | `getClassTree()` |
| GET | `/api/classes/<i>/timetable` | 班級課表（i＝real-classes.js 的索引）→ `{cls, codes, reqs, courses, note}` | `getClassTimetableById(i)` |
| GET | `/api/class-timetable?program=&dept=&grade=&cls=` | 同上，用學制／系所／年級／班別找 | `getClassTimetable()` |
| GET | `/api/courses?…` | 找課：`program dept grade day period(=3、E、5-9) from to q type eligible avail free limit offset` | 選課頁 runFind |
| GET | `/api/courses/<code>` | 單門課（code＝選課編號或「科目代碼@班級」） | `getCourse(code)` |
| GET | `/api/events?type=` | 行事曆（= SCU_REAL_EVENTS） | `getEvents()` |
| GET | `/api/news?limit=` | 公告（= SCU_REAL_NEWS） | `getNews()` |
| GET | `/api/selection/window[?at=]` | 現在能不能選課；`at` 只供預覽 | （新） |
| GET | `/api/me/timetable` | 我的課表 | `getMyTimetable()` |
| GET/POST/DELETE | `/api/cart` | 選課車（POST `{"code","action":"add"/"drop"}`；DELETE `?code=` 或全部） | `getCart()/saveCart()` |
| POST | `/api/cart/submit` | 送出（伺服器檢查） | 選課車「送出」 |
| GET | `/api/bundle/courses` | **與 real-courses.js 的 `SCU.REAL_COURSES` 完全相同** | `init()` |
| GET | `/api/bundle/classes` | **與 real-classes.js 的 `SCU.REAL_CLASSES` 完全相同** | `init()` |
| GET | `/api/bundle/events` | `{meta, events, news}` = real-events.js 三個變數 | `init()` |
| POST | `/api/login`、`/api/logout` | JSON 登入／登出（也有 HTML 版 `/accounts/login/`） | — |

課程物件欄位與前端 `decodeCourse()` 相同（`code no cid name teacher credits hours cap unlimited term group note ocls slots restr tba placeholder room dept program grade clsLabel general type listings enrolled`），另外多了：
`enrolledSimulated: true`（已選人數是模擬的）、`remain`、`eligible`（限修檢查結果）、`special`（第二專長等特殊課程標記，爬蟲新版才有）。

範例（節錄）：

```jsonc
// GET /api/profile
{"name":"王小明","studentId":"11316025","program":"學士班","dept":"資料科學系","grade":3,"cls":"B",
 "campus":"城中校區","college":"巨量資料管理學院","classLabel":"資科三B","username":"demo","demo":true,"authenticated":false}

// GET /api/courses?dept=資料科學系&grade=3&limit=1
{"count":16,"offset":0,"limit":1,"semester":"115-1","results":[{"code":"4248","no":"4248","cid":"BDD30101",
 "name":"資料探勘導論","teacher":"葉向原","credits":3,"cap":75,"slots":[{"day":1,"start":6,"end":7,"room":"H303","wk":""},
 {"day":4,"start":6,"end":7,"room":"H101","wk":"雙"}],"restr":{"g":[3],"src":"selrule","chk":1},"clsLabel":"資科三A",
 "type":"必修","enrolled":75,"enrolledSimulated":true,"remain":0,"eligible":{"ok":true,"reasons":[],"tags":[{"t":"限 三 年級","bad":false}]}}]}

// GET /api/selection/window（預設示範時間）
{"now":"2026-09-30T10:30:00+08:00","open":false,"canAdd":false,"canDrop":false,
 "reason":"目前（示範時間 2026/09/30 10:30）不是選課時段，不能加選、退選或送出選課。上一個選課時段「網路即時退選」已於 9/22（二）24:00 結束。下一個選課時段尚未公布。",
 "windows":[{"title":"開學後加退選③：全校所有課程","range":"9/17（四）20:00 ～ 9/18（五）16:00","kind":"select","course_scope":"all","applies":true,"status":"ended"}, …]}

// POST /api/cart {"code":"4338"}（不在選課時段）→ HTTP 403
{"ok":false,"error":"selection_closed","reason":"目前（示範時間 2026/09/30 10:30）不是選課時段，不能加選、退選或送出選課。…"}

// POST /api/cart/submit（示範時間 9/17 21:00 加退選③，選課車放了 3323）→ HTTP 409
{"ok":false,"error":"checks_failed","reason":"送出前檢查沒有通過：衝堂：「資料探勘導論」(4264) 與「會計學(三)下」(3323) 在星期四 第 5–6 節時間重疊；限修不符：「會計學(三)下」(3323)：限重補修生（一般修課不適用）","checks":{…}}
```

### 為什麼用「純 Django view」而不是 Django REST Framework（DRF）？
- 這個專案的 API 大多是**唯讀、形狀固定**（要跟前端現有格式一模一樣），用 `JsonResponse` 直接回 dict 最直覺，每一行都看得懂；
  DRF 的 Serializer／ViewSet／Router 很強大，但要先學一層抽象，報告時也比較難一眼說明「資料從哪裡來」。
- 需要的功能（GET 參數、JSON body、登入、CSRF、狀態碼）Django 本身都有。
- 之後 API 變多、要做權限或自動 API 文件時再換 DRF 也很容易：`catalog.py`、`checks.py`、`windows.py` 這些邏輯都不在 view 裡，可以直接沿用。

---

## 5. 選課檢查與「選課時段鎖定」（伺服器端）

**為什麼要在伺服器檢查？** 前端的檢查只是方便使用者；任何人都可以打開開發者工具或用 curl 直接 POST。
真正「算數」的規則一定要放在伺服器。

### 5.1 系統的「現在」（`enrollment/clock.py`）
1. admin →「示範時鐘」勾選啟用並填時間（最優先，展示時最方便）
2. `settings.SCU_DEMO_NOW`（預設 `2026-09-30T10:30`，可用環境變數 `set SCU_DEMO_NOW=2026-09-17T21:00` 改；`real` ＝真實時間）

送出時**只看伺服器時間**；`/api/selection/window?at=…` 只能預覽，POST 帶 `at` 也沒用（有測試）。

### 5.2 選課時段從哪來（`enrollment/windows.py`）
讀 `events.Event` 裡 `category="選課"` 的事件，優先用「學士班網路選課註冊時間表」，並從原始文字解析**時間**：
`"18 日 | 20:00 16:00 | 開學後加退選④：全校所有課程"` → 9/18 20:00 ～ 9/21 16:00。115-1 推出來的時段：

| 時段 | 時間 | 種類 | 開放範圍 | 對王小明 |
|---|---|---|---|---|
| 初選：網路登記選課 | 6/17 09:00 ～ 7/2 24:00 | 加＋退 | 全部 | 適用 |
| 第二專長網路登記選課 | 7/7 09:00 ～ 7/8 16:00 | 加＋退 | 第二專長 | 不適用 |
| 法律系／理學院／商學院 專業課程加退選 | 7/27、9/3、9/5 | 加＋退 | 學系專業 | 不適用（別的學院） |
| 人社院、外語學院、**巨量學院**各系專業課程 | 9/7 09:00 ～ 9/8 21:00 | 加＋退 | 學系專業 | 適用 |
| 共通科目及第二專長即時加退選 | 9/11 09:00 ～ 9/12 16:00 | 加＋退 | 共通科目（通識、國文、外文、體育、全校選修） | 適用 |
| 開學後加退選①② 學系專業課程 | 9/14、9/15 20:00 ～ 隔天 16:00 | 加＋退 | 學系專業 | 適用 |
| 開學後加退選③④ 全校所有課程 | 9/17 20:00 ～ 9/18 16:00、9/18 20:00 ～ 9/21 16:00 | 加＋退 | 全部 | 適用 |
| 網路即時退選 | 9/22 09:00 ～ 24:00 | **只能退** | 全部 | 適用 |
| 上網確認選課清單 | 10/1 ～ 10/8 | 只能確認 | — | 不能加退選 |

「人工加選」「結果查詢」「列印」不是線上選課時段，略過。沒有時間表時退回行事曆 ICS 的「加退選」整天事件。

### 5.3 擋在哪裡（`enrollment/views.py`）
- `POST /api/cart`：`_window_block()` 先檢查 → 不能加選回 **403** `selection_closed`；只開放學系專業／共通科目的階段加了範圍外的課 → **403** `course_not_open_in_phase`。
- `POST /api/cart/submit`：送出當下**再檢查一次**（選課車可能是時段內加的，送出時已關閉）→ **403**。
- 通過時段檢查後才做規則檢查（`enrollment/checks.py`），不通過回 **409** `checks_failed`，`reason` 是中文、`checks.messages` 是逐條原因：
  - **衝堂**：同一天節次重疊；單週 vs 雙週、前 9 週 vs 後 9 週不算；「時段保留」列不算
  - **學分**：送出後總學分要在 16–25（示範規則，`settings.SCU_CREDIT_RULE`）
  - **額滿（模擬）**：已選人數＝固定假數字（與前端同一個演算法）＋本系統送出的人數，訊息會寫「已選人數為模擬數字」
  - **限修**：年級、學制、系所（含簡稱比對）、班級、不可選學系、限重補修生、第二專長等特殊課程
- `DELETE /api/cart` 只是修改草稿，任何時候都可以。每次送出（成功或被擋）都記在 `Submission`，可在 admin 查看。

---

## 6. 管理指令（manage.py 自訂指令）

| 指令 | 連網？ | 說明 |
|---|---|---|
| `import_timetable_db --semester 115-1 [--db 路徑]` | 否 | 從 scu_timetable.db 匯入一學期（約 1 秒，整學期換新、transaction 保護）。爬蟲新增的欄位自動放進 `extra` |
| `import_events_db [--db 路徑]` | 否 | 從 scu_events.db 匯入事件與公告（upsert，可重複跑） |
| `setup_demo [--reset]` | 否 | 建立 demo/demo1234（王小明）與資科三B 初始課表；`--reset` 清掉重來 |
| `crawl_timetable --semester 115-1 [--program 學士班 --dept 資料科學系 --limit N --dry-run]` | 是 | 全校課表，約 520 個請求、≥1.2 秒/請求、10–15 分鐘 |
| `crawl_rules --semester 115-1 --dept 資料科學系 …｜--all` | 是 | 選課限制（限修）；--all 約 2,900 個請求、1 小時以上 |
| `crawl_events [--only calendar,news]` | 是 | 行事曆 ICS＋PDF＋選課時間表＋公告，約 10–18 個請求，≥1.5 秒/請求 |
| `crawl_announcements [--pages 2]` | 是 | 只抓公告（crawl_events --only news 的捷徑），約 2–5 個請求 |
| `sync_frontend --src ..\scu-portal-demo` | 否 | 複製前端網站到 frontend/（只讀來源） |

爬蟲禮儀：請求間隔 ≥1.2 秒（課表）／≥1.5 秒（行事曆），遇到 HTTP 403／429 立即停止；原始 HTML 存在 `raw/`，
解析有錯可以不連網重跑。行事曆 PDF 需要 poppler 的 `pdftotext`（`winget install oschwartz10612.Poppler`），沒有也不影響 ICS 與公告。

---

## 7. 排程（Windows 工作排程器 schtasks）

| 工作 | 批次檔 | 頻率 | 理由 |
|---|---|---|---|
| 全校課表＋限修 | `scripts\crawl_timetable.bat 115-2` | **每學期 1 次，初選前**（學校公布課表後）；可選加退選前再 1 次 | 課表一學期只公布一次；加退選前教室、教師、人數上限可能變 |
| 行事曆＋選課時間表 | `scripts\crawl_calendar.bat` | **每週 1 次**（週一 06:30）；開學前後可改每天 | 行事曆偶爾「另行公告」異動 |
| 校園公告 | `scripts\crawl_news.bat` | **每天 2 次**（07:30、17:30） | 每天都有新公告 |

用「系統管理員」開 cmd（路徑換成你的專案位置）：

```bat
:: 公告：每天 07:30、17:30
schtasks /Create /TN "SCU\crawl_news_am" /TR "C:\Users\AUSER\Desktop\scu-backend\scripts\crawl_news.bat" /SC DAILY /ST 07:30 /F
schtasks /Create /TN "SCU\crawl_news_pm" /TR "C:\Users\AUSER\Desktop\scu-backend\scripts\crawl_news.bat" /SC DAILY /ST 17:30 /F

:: 行事曆：每週一 06:30
schtasks /Create /TN "SCU\crawl_calendar" /TR "C:\Users\AUSER\Desktop\scu-backend\scripts\crawl_calendar.bat" /SC WEEKLY /D MON /ST 06:30 /F

:: 課表：一學期一次。例：115-2 初選前（2027-01 某天 02:00）跑一次；加退選前再一次
schtasks /Create /TN "SCU\crawl_timetable_115-2" /TR "C:\Users\AUSER\Desktop\scu-backend\scripts\crawl_timetable.bat 115-2" /SC ONCE /SD 2027/01/04 /ST 02:00 /F
schtasks /Create /TN "SCU\crawl_timetable_115-2_adddrop" /TR "C:\Users\AUSER\Desktop\scu-backend\scripts\crawl_timetable.bat 115-2" /SC ONCE /SD 2027/02/18 /ST 02:00 /F

:: 立即測試、查看、刪除
schtasks /Run /TN "SCU\crawl_news_am"
schtasks /Query /TN "SCU\crawl_news_am" /V /FO LIST
schtasks /Delete /TN "SCU\crawl_news_am" /F
```

（`/SD` 日期格式依 Windows 地區設定，台灣通常是 `YYYY/MM/DD`。）紀錄寫在 `logs\*.log`。
115-2 的日期請等學校公布「選課註冊時間表」後再定；爬完行事曆，`/api/selection/window` 就會自動出現新學期的時段。

---

## 8. 前端網站怎麼接（下一步的計畫）

現在 `/` 是佔位頁；`/js/…`、`/css/…` 已經會從 `frontend/` 提供檔案。等另一位同學改完 `scu-portal-demo`（第二專長標記、選課時段鎖定）後：

1. `python manage.py sync_frontend --src ..\scu-portal-demo` → 打開 <http://127.0.0.1:8000/> 就是入口網站（仍讀 real-*.js，確認一切正常）。
2. **最小改動**：只改 `js/data-source.js` 的 `init()`，把三個全域變數改成從 API 拿（格式完全一樣，已驗證逐筆相同）：
   ```js
   init() {
     const j = (u) => fetch(u, { credentials: 'same-origin' }).then((r) => r.json());
     return Promise.all([j('/api/bundle/courses'), j('/api/bundle/classes'), j('/api/bundle/events'), j('/api/profile')])
       .then(([c, k, ev, p]) => {
         S.REAL_COURSES = c; S.REAL_CLASSES = k;
         window.SCU_REAL_EVENTS = ev.events; window.SCU_REAL_NEWS = ev.news; window.SCU_REAL_META = ev.meta;
         S.PROFILE = p;
         /* …原本 init() 的內容照舊… */
       });
   }
   ```
   然後 `index.html` 拿掉三個 `<script src="js/real-*.js">`。`main.js` 本來就等 `init()` 完成才畫面，不用改。
3. **選課改走伺服器**：`saveCart()` → `POST/DELETE /api/cart`；選課車「送出」→ `POST /api/cart/submit`，把 403／409 的 `reason` 直接顯示；
   `getMyTimetable()` 用 `/api/me/timetable`；選課頁上方顯示 `/api/selection/window` 的 `reason`，`canAdd=false` 時把「加入選課車」按鈕停用。
   POST 要帶 CSRF：`headers: {'Content-Type': 'application/json', 'X-CSRFToken': 從 document.cookie 讀 csrftoken}`（先呼叫過 `/api/profile` 就有 cookie）。
4. 示範時間：前端 `config.js` 的 `DEMO_NOW` 與伺服器的 `SCU_DEMO_NOW` 要一致（之後可改成前端從 `/api/selection/window` 的 `now` 讀）。
5. 找課可以繼續在前端篩（資料量 600 KB 還行），或改呼叫 `/api/courses?…`（伺服器篩、分頁）。

---

## 9. 寫報告用：哪段程式教哪個概念

| 概念 | 看哪裡 |
|---|---|
| 專案 vs app、INSTALLED_APPS | `config/settings.py` |
| URL 路由、`include()`、路徑參數 `<int:class_index>` `<str:code>` | `config/urls.py`、`timetable/urls.py` |
| Model 與欄位型別、`ForeignKey`、`ManyToManyField(through=)`、`OneToOneField` | `timetable/models.py`、`accounts/models.py` |
| 抽象基底類別（abstract model 繼承） | `timetable/models.py` 的 `ScrapedModel` |
| 唯一限制、索引、`TextChoices`/`IntegerChoices` | `timetable/models.py` Meta、`enrollment/models.py` |
| Migrations（資料表版本） | 各 app 的 `migrations/0001_initial.py`，`makemigrations`／`migrate` |
| ORM 查詢：`filter`、`values`、`aggregate`、`annotate(Count)`、`Cast` | `timetable/catalog.py`、`enrollment/seats.py`、`events/services.py` |
| `bulk_create`、`update_or_create`、`transaction.atomic` | `timetable/management/commands/import_timetable_db.py` |
| Function-based view、`@require_GET/POST`、`JsonResponse`、HTTP 狀態碼 403/409 | `timetable/views.py`、`enrollment/views.py`、`config/api.py` |
| 認證：`authenticate`/`login`、session、內建 `LoginView`、模板 | `accounts/views.py`、`config/urls.py`、`accounts/templates/` |
| CSRF 保護與 `ensure_csrf_cookie` | `accounts/views.py`（第 5 節也有說明） |
| 商業邏輯從 view 抽出來（service layer） | `enrollment/services.py`、`checks.py`、`windows.py` |
| 自訂管理指令、`call_command` | `*/management/commands/*.py`、`crawl_announcements.py` |
| Django admin：`list_display`、`list_filter`、`search_fields`、Inline | 各 app 的 `admin.py` |
| 時區（`USE_TZ`、`Asia/Taipei`、aware datetime） | `config/settings.py`、`enrollment/clock.py` |
| 自訂設定＋ `override_settings` 測試 | `settings.py` 的 `SCU_*`、`enrollment/tests.py` |
| 自動測試（TestCase、測試用資料庫、Client） | `enrollment/tests.py`、`timetable/tests.py` |
| 記憶體快取與失效（version） | `timetable/catalog.py` |
| 爬蟲禮儀（間隔、403/429 停止、原始檔保存） | `timetable/scu/class40.py`、`events/crawler/scu_common.py` |
| 靜態檔案（開發用 `static.serve`；上線用 WhiteNoise／nginx） | `portal/views.py` |

---

## 10. 常見問題

- **POST 回 403 但內容是 HTML「CSRF verification failed」**：那是 Django 的 CSRF 保護，不是選課時段。要帶 `X-CSRFToken` header（見第 8 節）。選課時段的 403 一定是 JSON，`error` 是 `selection_closed`。
- **改示範時間**：admin →「示範時鐘」新增一筆、勾「啟用」，例如 2026-09-17 21:00（加退選③）；取消勾選就回到預設 9/30 10:30。
- **重新匯入**：`import_timetable_db` 會先刪除該學期課程再匯入；使用者的課表存的是「選課編號」字串，不會被刪掉。
- **換學期**：爬新學期（或匯入新的 scu_timetable.db）→ 設 `SCU_SEMESTER=115-2`（環境變數或 settings）→ `setup_demo --reset`。
- **admin 登入**：先 `python manage.py createsuperuser`。demo 帳號不是管理員。

## 11. 資料來源與限制
- 課程、班級、限修：東吳大學公開課表 `web.sys.scu.edu.tw/class40.asp`、選課限制查詢 `selrule12.asp`（不需登入）。限修只完整抓了資料科學系與共通科目相關課程，其他課程只用備註推測（`restr.chk=0`＝「限修未查」）。
- 行事曆：教務處 Google 日曆 ICS、115 學年行事曆 PDF、學士班網路選課註冊時間表 PDF；公告：news.scu.edu.tw（只存標題、日期、單位）。
- 已選人數**沒有公開資料**，一律是模擬數字（`enrolledSimulated: true`）。學分 16–25 是示範規則。實際以學校公告與選課系統為準。
