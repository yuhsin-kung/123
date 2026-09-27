# trade-rag paths (keep separate from Desktop\trade)
"""全域設定。所有「可以改」的東西都集中在這裡，並可用環境變數覆寫。

教學重點：設定集中管理 → 程式其他地方只 import 這裡的常數，
要換模型、換示範時間、換資料庫路徑時不必改邏輯程式。
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_DIR = ROOT / "data" / "rules"
EVAL_DIR = ROOT / "data" / "eval"
INDEX_DIR = ROOT / "indexes"

# Domain stores stay SEPARATE under INDEX_DIR/<store>/（一個資料夾＝一個 store）
#   trade   交易規則手冊（原本就有）
#   scu     東吳學校資料：行事曆、公告、選課時段與政策文字（scu_ingest.py 產生）
#   general 一般聊天的「主題樣本」小庫（build_router.py 產生，只給路由器打分用）
#   course / admit  舊的空白佔位（沒有索引檔就自動略過）
STORE_NAMES = ("trade", "course", "admit")
# 新建的 store 先放 indexes/_pending/<store>/（「待上線」）：
#   舊版 chat_ui.py（7860）只掃 indexes/ 第一層，看不到 _pending → 不會被新資料影響；
#   v2（7861）兩邊都掃。確認沒問題後把資料夾搬到 indexes/ 就算正式上線。
PENDING_INDEX_DIR = INDEX_DIR / "_pending"
STORE_CONFIG_NAME = "store.json"  # 可選：{"topic": "school", "label": "...", "threshold": 0.5}
DEFAULT_STORE = "trade"
TRADE_INDEX_DIR = INDEX_DIR / DEFAULT_STORE

# Ingest/build write trade rules into indexes/trade/
CHUNKS_PATH = TRADE_INDEX_DIR / "chunks.jsonl"
FAISS_NAME = "index.faiss"
META_NAME = "index_meta.pkl"
# 路由用的「錨點問句」索引（與內容索引分開，不影響原本的 RAG 檢索結果）
ANCHOR_FAISS_NAME = "anchors.faiss"
ANCHOR_META_NAME = "anchors_meta.pkl"

EMBED_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# ---- 本地 LLM（Ollama，免費、本機） ----
OLLAMA_URL = os.environ.get("TRADE_RAG_OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
CHAT_MODEL = os.environ.get("TRADE_RAG_CHAT_MODEL", "qwen2.5:3b")
# 新增的學校／一般聊天路徑讓模型在記憶體多留幾分鐘，連續對話比較快；
# 原本交易路徑仍維持 keep_alive=0（不改舊行為）。
KEEP_ALIVE = os.environ.get("TRADE_RAG_KEEP_ALIVE", "5m")
BOT_NAME = os.environ.get("TRADE_RAG_BOT_NAME", "阿斯拉")

# ---- 學校資料（scu-backend，唯讀） ----
SCU_BACKEND_DIR = Path(os.environ.get("SCU_BACKEND_DIR", r"C:\Users\AUSER\Desktop\scu-backend"))
SCU_DB = Path(os.environ.get("SCU_DB", str(SCU_BACKEND_DIR / "db.sqlite3")))
SCU_SEMESTER = os.environ.get("SCU_SEMESTER", "115-1")
# 現在時間（台北）。預設跟系統時鐘；要鎖回示範日再設 TRADE_RAG_DEMO_NOW=2026-09-30T10:30
SCU_DEMO_NOW = os.environ.get("TRADE_RAG_DEMO_NOW", "real")
# 預設學生（個人化問題用；API 可用 profile 欄位覆寫）
DEFAULT_PROFILE = {
    "name": os.environ.get("TRADE_RAG_PROFILE_NAME", "王小明"),
    "program": os.environ.get("TRADE_RAG_PROFILE_PROGRAM", "學士班"),
    "dept": os.environ.get("TRADE_RAG_PROFILE_DEPT", "資料科學系"),
    "college": os.environ.get("TRADE_RAG_PROFILE_COLLEGE", "巨量資料管理學院"),
    "grade": int(os.environ.get("TRADE_RAG_PROFILE_GRADE", "3")),
    "cls": os.environ.get("TRADE_RAG_PROFILE_CLS", "B"),
    "student_id": os.environ.get("TRADE_RAG_PROFILE_SID", "11316025"),
}
SCU_DATA_DIR = ROOT / "data" / "scu"

# ---- 路由器 ----
ROUTER_DIR = ROOT / "data" / "router"
ROUTER_THRESHOLDS = ROUTER_DIR / "thresholds.json"
ROUTER_LLM_FALLBACK = os.environ.get("TRADE_RAG_ROUTER_LLM", "0") == "1"
GENERAL_DATA_DIR = ROOT / "data" / "general"

LOG_DIR = ROOT / "logs"
ROUTE_LOG = LOG_DIR / "route_log.jsonl"
