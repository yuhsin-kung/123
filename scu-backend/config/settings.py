"""
config/settings.py — 整個 Django 專案的設定檔

讀報告時的重點：
  * INSTALLED_APPS：列出本專案自己寫的 5 個 app（timetable / events / accounts / enrollment / portal）
  * DATABASES：SQLite（一個檔案 db.sqlite3，免安裝資料庫伺服器）
  * TIME_ZONE / LANGUAGE_CODE：台北時區、繁體中文（admin 介面會變中文）
  * 最下面 SCU_* 是本專案自訂的設定（示範時間、學分規則、資料檔路徑…）
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# 開發用金鑰：正式上線請改用環境變數 DJANGO_SECRET_KEY
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-scu-portal-demo-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # ---- 本專案的 app ----
    "timetable",    # 課程、班級、節次、限修條件、爬蟲紀錄
    "events",       # 行事曆事件、校園公告
    "accounts",     # 示範學生資料（王小明）＋登入
    "enrollment",   # 選課車、送出檢查、選課時段鎖定
    "portal",       # 提供前端網站（index.html、js、css）
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "zh-hant"
TIME_ZONE = "Asia/Taipei"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"   # python manage.py collectstatic 的輸出位置（上線才需要）

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# ======================================================================
# 本專案自訂設定（程式裡用 settings.SCU_xxx 讀取）
# ======================================================================
SCU_SEMESTER = os.environ.get("SCU_SEMESTER", "115-1")

# 示範用的「現在」：選課時段鎖定、行事曆倒數都用它判斷。
#   * 預設 2026-09-30 10:30（台北時間）＝加退選已結束 → 選課車會被鎖住
#   * 環境變數 SCU_DEMO_NOW=2026-09-17T21:00 可改；設成 "real" 則用真正的現在時間
#   * 也可以在 admin 的「示範時鐘」(DemoClock) 改，admin 設定優先
SCU_DEMO_NOW = os.environ.get("SCU_DEMO_NOW", "2026-09-30T10:30")

# 學分上下限（示範規則，非學校正式規定；與前端 data-courses.js 的 CREDIT_RULE 相同）
SCU_CREDIT_RULE = {"min": 16, "max": 25}

# 沒登入時，API 是否自動當作示範學生（demo 帳號）。黑客松展示方便；正式系統要設 False。
SCU_DEMO_AUTOLOGIN = os.environ.get("SCU_DEMO_AUTOLOGIN", "1") == "1"
SCU_DEMO_USERNAME = "demo"

# 匯入指令預設讀的 SQLite 檔（爬蟲產生的；data/ 內是複製過來的快照）
SCU_TIMETABLE_DB = BASE_DIR / "data" / "scu_timetable.db"
SCU_EVENTS_DB = BASE_DIR / "data" / "scu_events.db"

# 爬蟲原始 HTML 存放處（crawl_timetable / crawl_rules 用）
SCU_RAW_DIR = BASE_DIR / "raw"

# 前端網站資料夾：http://127.0.0.1:8000/ 會提供這裡的 index.html、js/、css/
# 之後用 `python manage.py sync_frontend --src ..\scu-portal-demo` 複製一份進來
SCU_FRONTEND_DIR = BASE_DIR / "frontend"
