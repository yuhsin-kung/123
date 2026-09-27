# -*- coding: utf-8 -*-
"""主題路由器（intent router）：每一句話先決定要交給哪個「主題」處理。

主題（topic）與對應的知識庫（store）：
  trade   → indexes/trade   交易規則＋即時帳戶／個股（原本的功能）
  school  → indexes/scu     東吳學校資料（行事曆、公告、選課時段、政策；課表走 SQL）
  general → indexes/general 一般聊天主題樣本（沒有檢索，只給路由打分）
  clarify → 不確定時先反問一句，不亂猜

判斷流程（由上到下，先命中先決定）：
  0. mode 參數：API／UI 指定主題就直接用（例如交易 chips 送 mode=trade）
  1. 反問的回覆：上一輪是 clarify，這輪回「股票／學校／一般」→ 用原本的問題重跑
  2. 股票實體偵測（最優先的規則）：持倉／自選清單的名稱或代號（世紀、5314…）
       → 直接 trade（個股簡報），因為即時價格／持倉問題在文件庫裡根本沒有相似文件
       → 但同時出現學校結構化訊號（「世紀有什麼課」）→ clarify
  3. 硬規則：既有的交易「動作」（個股簡報、帳戶／持倉、三大法人、加權、夜盤）
             與學校「結構化查詢」（課表、選課時段、公告、班級、課名＋老師／教室）
  4. 多層資料庫打分（核心演算法）：
       query 只 embed 一次 → 對每個 store 找最相似的向量（內容＋錨點問句）得到 sim
       每個 store 有**自己的門檻** thr（在標註評測集上校準，data/router/thresholds.json）
       margin = sim − thr；不同 store 的原始相似度不直接比較，只比「超過自己門檻多少」
       主題延續：短追問（「那星期四呢？」）且上一輪主題是 X → X 的 margin 加 cont_bias
       沒有任何 margin > 0 → general（或延續上一個主題）
       trade 與 school 都 > 0 且差距 < clarify_gap → clarify
       否則取 margin 最大者
每一次判斷都寫進 logs/route_log.jsonl（含各 store 分數），報告可以直接引用。
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

from config import ROUTER_LLM_FALLBACK, ROUTER_THRESHOLDS

# 固定的三個主題 → store；其他 store 資料夾會自動被發現並成為新主題（見 topic_stores()）
BASE_TOPICS = {"trade": "trade", "school": "scu", "general": "general"}
TOPIC_LABELS = {"trade": "交易／股票", "school": "學校", "general": "一般聊天"}
DEFAULT_THRESHOLDS = {"trade": 0.50, "school": 0.50, "general": 0.55, "clarify_gap": 0.04, "cont_bias": 0.10}
UNKNOWN_STORE_THRESHOLD = 0.60

PUNCT_RE = re.compile(r"[\s，。！？、,.!?；;：:「」『』（）()\[\]【】~～…\-]+")

# ---- 交易硬規則（只放「既有的交易動作」，規則題交給打分） ----
BRIEF_KEYS = ("個股簡報", "各股簡報", "持股簡報", "持倉簡報", "持股狀態", "持倉狀態")
HOLDING_KEYS = ("帳戶", "持倉", "持股", "部位", "盤勢", "我的現金", "能開多少", "開多少", "還能買", "多少倉")
MARKET_RE = re.compile(r"(三大法人|外資|投信|自營商|買賣超|加權指數|加權(?!平均|分數|總分|成績|值|和|係數|後)|TWII|大盤|台股指數|夜盤|台指期|期貨盤後)")
# 股票實體後面如果只剩這些字 → 就是在問那檔股票
STOCK_STATUS_WORDS = ("現況", "狀態", "狀況", "近況", "怎麼樣", "怎樣", "如何", "今天", "今日", "最近", "新聞", "熱度",
                      "股價", "價量", "走勢", "簡報", "可以買嗎", "能買嗎", "現在", "目前", "分析", "財報", "營收",
                      "表現", "消息", "多少", "漲", "跌", "的", "呢", "嗎", "了", "嘛", "啊", "還", "好", "它", "那")
TRADE_CONTEXT_WORDS = ("股", "買", "賣", "進場", "出場", "持有", "漲", "跌", "K線", "成交", "盤", "價", "財報", "營收",
                       "法人", "熱度", "簡報", "張")

# ---- 學校結構化硬規則（精確查詢才需要規則；行事曆類交給打分） ----
SCHOOL_HARD_RE = re.compile(r"(有什麼課|有哪些課|有課|沒課|什麼課|哪些課|課表|第\s*[0-9一二三四五六七八九EA-D]{1,2}\s*節|幾點上課|"
                            r"選課|加退選|加選|退選|初選|公告|最新消息|校園消息|行事曆|校曆)")
COURSE_LOOKUP_RE = re.compile(r"(誰教|老師|教授|教室|學分|上課時間|星期幾|選課編號|哪裡上|哪間)")

FOLLOWUP_START_RE = re.compile(r"^(那|那麼|所以|還有|然後|另外|它|他|她|這個|那個|這|換|改)")
CONFUSED_RE = re.compile(r"^(看不懂|聽不懂|看不明|什麼意思|再說一次|聽不明|不懂|蛤|咦)[啊阿耶喔哦了嗎]?$")
VAGUE_WORDS = ("今天", "今日", "現在", "目前", "最近", "怎麼樣", "怎樣", "如何", "狀況", "情況", "還好嗎", "呢", "了", "啦", "的", "嗎")

CLARIFY_TAIL = "（回覆「股票」、「學校」或「一般」即可）"
CHOICE_TRADE = ("股票", "交易", "股", "盤", "持股", "trade")
CHOICE_SCHOOL = ("學校", "東吳", "課", "school", "校")
CHOICE_GENERAL = ("一般", "聊天", "其他", "都不是", "閒聊", "general", "隨便")


@dataclass
class Decision:
    route: str
    sub: str | None = None
    stage: str = ""
    reason: str = ""
    question: str = ""
    scores: dict = field(default_factory=dict)
    confidence: float = 1.0
    clarify: dict | None = None
    entity: list | None = None
    prev_topic: str | None = None
    followup: bool = False
    params: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# 門檻
# ---------------------------------------------------------------------------
_thr_cache: dict = {}


def thresholds() -> dict:
    try:
        mt = ROUTER_THRESHOLDS.stat().st_mtime
    except OSError:
        return dict(DEFAULT_THRESHOLDS)
    if _thr_cache.get("mt") != mt:
        data = json.loads(ROUTER_THRESHOLDS.read_text(encoding="utf-8"))
        t = dict(DEFAULT_THRESHOLDS)
        t.update({k: float(v) for k, v in (data.get("thresholds") or {}).items()})
        _thr_cache.update(mt=mt, t=t)
    return dict(_thr_cache["t"])


def topic_stores() -> dict[str, str]:
    """{topic: store}。走訪 indexes/ 與 indexes/_pending/：一個資料夾＝一個 store。
    store.json 的 "topic" 可指定主題名（scu → school）；沒寫就用資料夾名稱當主題。"""
    import time

    from stores import discover_all_stores, store_config

    hit = _topic_cache.get("v")
    if hit and time.time() - hit[0] < 5:
        return dict(hit[1])
    out = dict(BASE_TOPICS)
    for name in discover_all_stores():
        if name in out.values():
            continue
        topic = store_config(name).get("topic") or name
        out.setdefault(topic, name)
    _topic_cache["v"] = (time.time(), dict(out))
    return out


_topic_cache: dict = {}


def topic_label(topic: str) -> str:
    if topic in TOPIC_LABELS:
        return TOPIC_LABELS[topic]
    from stores import store_config

    return store_config(topic_stores().get(topic, topic)).get("label") or topic


def _thr_for(thr: dict, topic: str) -> float:
    if topic in thr:
        return thr[topic]
    from stores import store_config

    return float(store_config(topic_stores().get(topic, topic)).get("threshold") or UNKNOWN_STORE_THRESHOLD)


# ---------------------------------------------------------------------------
# 1) 多層資料庫打分
# ---------------------------------------------------------------------------
def store_sims(q: str) -> dict:
    """query 只 embed 一次，對每個 store 取最相似的一筆（內容索引與錨點索引取較大者）。"""
    from embedder import encode_query
    from stores import cached_store

    v = encode_query(q)
    out = {}
    for topic, store in topic_stores().items():
        handle, anchors = cached_store(store)
        best, best_txt, via = -1.0, "", ""
        if handle is not None and handle.index.ntotal:
            D, I = handle.index.search(v, 1)
            if I[0][0] >= 0 and float(D[0][0]) > best:
                c = handle.meta["chunks"][int(I[0][0])]
                best, best_txt, via = float(D[0][0]), str(c.get("heading") or c.get("title") or "")[:40], "content"
        if anchors is not None and anchors[0].ntotal:
            D, I = anchors[0].search(v, 1)
            if I[0][0] >= 0 and float(D[0][0]) > best:
                best, best_txt, via = float(D[0][0]), anchors[1]["texts"][int(I[0][0])][:40], "anchor"
        out[topic] = {"sim": round(best, 4), "best": best_txt, "via": via, "store": store}
    return out


def decide_from_sims(sims: dict, thr: dict, prev_topic: str | None, followup: bool) -> tuple[str, str, float, dict]:
    """純函式（方便校準與單元測試）：sim ＋ 門檻 → (route, reason, confidence, margins)。"""
    margins = {t: sims[t]["sim"] - _thr_for(thr, t) for t in sims}
    adj = dict(margins)
    if followup and prev_topic in adj:
        adj[prev_topic] += thr["cont_bias"]
    pos = sorted(((m, t) for t, m in adj.items() if m > 0), reverse=True)
    if not pos:
        if followup and prev_topic in adj:
            return prev_topic, f"沒有 store 超過門檻，短追問 → 延續上一個主題 {prev_topic}", 0.4, adj
        return "general", "沒有任何 store 超過自己的門檻 → 一般聊天", 0.5, adj
    top_m, top_t = pos[0]
    if len(pos) > 1:
        sec_m, sec_t = pos[1]
        if top_t != "general" and sec_t != "general" and top_m - sec_m < thr["clarify_gap"]:
            return "clarify", f"{top_t} 與 {sec_t} 都過門檻且差距 {top_m - sec_m:.3f} < {thr['clarify_gap']}", 0.3, adj
        conf = min(1.0, 0.5 + (top_m - sec_m) * 5)
    else:
        conf = min(1.0, 0.6 + top_m * 4)
    why = f"{top_t} margin {top_m:+.3f} 最高"
    if followup and prev_topic == top_t:
        why += f"（含延續加權 +{thr['cont_bias']}）"
    return top_t, why, round(conf, 3), adj


# ---------------------------------------------------------------------------
# 2) 規則：股票實體、交易動作、學校結構化
# ---------------------------------------------------------------------------
def detect_stock_entity(q: str) -> tuple[str, str] | None:
    """持倉＋自選清單（paper/ui_settings.json、account.json，唯讀）裡的名稱或代號。"""
    from stock_brief import _load_watchlist

    try:
        watch = _load_watchlist()
    except Exception:
        watch = {}
    for t, name in sorted(watch.items(), key=lambda kv: -len(kv[1] or "")):
        if name and len(name) >= 2 and name in q:
            return t, name
    for m in re.finditer(r"(?<![\d.])(\d{4})(?:\.(TW|TWO))?(?![\d])", q, re.I):
        code, suf = m.group(1), (m.group(2) or "").upper()
        if suf:
            return f"{code}.{suf}", watch.get(f"{code}.{suf}", code)
        for c in (f"{code}.TW", f"{code}.TWO"):
            if c in watch:
                return c, watch[c]
    return None


def _strip(q: str) -> str:
    return PUNCT_RE.sub("", q or "")


def _remainder_after_entity(q: str, ent: tuple[str, str]) -> str:
    t = _strip(q).replace(ent[1], "").replace(ent[0], "").replace(ent[0].split(".")[0], "")
    for w in sorted(STOCK_STATUS_WORDS, key=len, reverse=True):
        t = t.replace(w, "")
    return t


def hard_trade(q: str) -> str | None:
    if any(k in q for k in BRIEF_KEYS):
        return "個股簡報關鍵字"
    if any(k in q for k in HOLDING_KEYS):
        return "帳戶／持倉／盤勢關鍵字"
    m = MARKET_RE.search(q)
    if m:
        return f"行情關鍵字「{m.group(0)}」"
    return None


def hard_school(q: str) -> str | None:
    import scu_tools as T

    try:
        lab = T.find_class_label(q)
        if lab:
            return f"班級「{lab}」"
        m = SCHOOL_HARD_RE.search(q)
        if m:
            return f"學校結構化關鍵字「{m.group(0)}」"
        names = T.find_course_names(q)
        if names and COURSE_LOOKUP_RE.search(q):
            return f"課名「{names[0]}」＋查詢詞"
    except Exception:
        return None
    return None


def is_followup(q: str) -> bool:
    s = _strip(q)
    if not s or len(s) > 14:
        return False
    return bool(FOLLOWUP_START_RE.match(s)) or s.endswith("呢") or "它" in s or is_confused(q)


def is_confused(q: str) -> bool:
    s = (q or "").strip()
    if s in ("?", "？"):
        return True
    return bool(CONFUSED_RE.match(_strip(s)))


def _last_user(history: list[dict] | None) -> str:
    for h in reversed(history or []):
        if h.get("role") == "user" and str(h.get("content") or "").strip():
            return str(h["content"])
    return ""


def is_vague(q: str) -> bool:
    s = _strip(q)
    if not s or len(s) > 7:
        return False
    if not any(w in s for w in ("今天", "今日", "現在", "目前", "最近")):
        return False
    for w in sorted(VAGUE_WORDS, key=len, reverse=True):
        s = s.replace(w, "")
    return s == ""


def _prev_topic(history: list[dict] | None) -> tuple[str | None, str]:
    """上一個主題：優先讀 history 裡 assistant 訊息附帶的 route；沒有就用上一句 user 重算。"""
    prev_user = ""
    for h in reversed(history or []):
        if h.get("role") == "assistant" and h.get("route") and h.get("route") != "clarify":
            return h["route"], ""
    for h in reversed(history or []):
        if h.get("role") == "user" and str(h.get("content") or "").strip():
            prev_user = str(h["content"])
            break
    if prev_user:
        d = route(prev_user, None, None, _log=False, _sub=False)
        if d.route != "clarify":
            return d.route, prev_user
    return None, prev_user


def _last_clarify(history: list[dict] | None) -> tuple[str | None, dict | None]:
    if not history:
        return None, None
    last = history[-1]
    if last.get("role") != "assistant":
        return None, None
    if last.get("route") == "clarify" or CLARIFY_TAIL in str(last.get("content") or ""):
        pending = (last.get("clarify") or {}).get("pending_question")
        if not pending:
            for h in reversed(history[:-1]):
                if h.get("role") == "user":
                    pending = str(h.get("content") or "")
                    break
        return pending, last.get("clarify")
    return None, None


def _choice(reply: str, options: list[str] | None = None) -> str | None:
    s = _strip(reply)
    if len(s) > 12:
        return None
    for topic, words in (("trade", CHOICE_TRADE), ("school", CHOICE_SCHOOL), ("general", CHOICE_GENERAL)):
        if any(w in s for w in words):
            return topic
    for t in options or []:  # 自動發現的新主題：回覆主題名稱或標籤
        if t in s or topic_label(t) in s:
            return t
    return None


def _clarify(question: str, text: str, options: list[str], stage: str, reason: str, **kw) -> Decision:
    return Decision(route="clarify", sub=None, stage=stage, reason=reason, question=question, confidence=0.3,
                    clarify={"question": text + CLARIFY_TAIL, "options": options, "pending_question": question}, **kw)


def _llm_topic(q: str) -> str | None:
    """可選：打分不確定時請本機小模型選一個主題（預設關閉，TRADE_RAG_ROUTER_LLM=1 開啟）。"""
    from llm import chat

    try:
        out = chat([{"role": "system", "content": "你是分類器。只輸出一個英文單字：trade（股票交易、帳戶、交易規則）、"
                                                  "school（東吳大學課程、選課、行事曆、公告）、general（其他）、unsure。"},
                    {"role": "user", "content": q}], temperature=0.0, num_predict=5, timeout=30, with_clock=False)
    except Exception:
        return None
    out = out.strip().lower()
    for t in ("trade", "school", "general"):
        if out.startswith(t):
            return t
    return None


# ---------------------------------------------------------------------------
# 主函式
# ---------------------------------------------------------------------------
def _with_sub(d: Decision, history: list[dict] | None) -> Decision:
    if d.route == "trade":
        from answer import resolve_ticker, trade_subroute

        q = d.question
        # 路由器認得股票（例如「5314今天」），但原本的 resolve_ticker 因為沒空格抓不到 → 補上代號名稱
        if d.entity and resolve_ticker(q) is None:
            q = f"{d.entity[0]} {d.entity[1]} {q}"
            d.question = q
        d.sub = trade_subroute(q)[0]
    elif d.route == "school":
        from scu_answer import school_subroute

        d.sub, d.params = school_subroute(d.question, history)
    elif d.route == "general":
        d.sub = "chat"
    elif d.route != "clarify":
        d.sub = "grounded_rag"  # 自動發現的 store：通用「只根據檢索內容」回答
    return d


def route(message: str, history: list[dict] | None = None, mode: str | None = None,
          _log: bool = True, _sub: bool = True) -> Decision:
    q = (message or "").strip()
    thr = thresholds()
    d = _route(q, history, mode, thr)
    if _sub:
        d = _with_sub(d, history)
    return d


def _route(q: str, history, mode, thr) -> Decision:
    # 0) 指定主題
    if mode and (mode in ("trade", "school", "general") or mode in topic_stores()):
        return Decision(route=mode, stage="mode", reason=f"mode={mode}", question=q)

    # 1) 反問的回覆
    pending, cinfo = _last_clarify(history)
    if pending:
        pick = _choice(q, (cinfo or {}).get("options"))
        if pick:
            d = _route(pending, None, pick, thr)
            d.stage, d.reason = "clarify_reply", f"使用者回覆「{q}」→ {pick}，重跑原問題「{pending}」"
            if pick == "trade":
                ent = detect_stock_entity(pending)
                d.entity = list(ent) if ent else None
            return d

    followup = is_followup(q)
    prev_topic, _prev_user_q = (None, "")
    if history:
        prev_topic, _prev_user_q = _prev_topic(history)

    # 1b) 「看不懂／？」：不要重打分（短句常被交易規則庫吸走），延續上一題
    if history and prev_topic and is_confused(q):
        prev_q = _last_user(history) or _prev_user_q or q
        return Decision(route=prev_topic, stage="confused_followup",
                        reason="表示沒看懂 → 延續上一主題並重答上一題", question=prev_q,
                        followup=True, prev_topic=prev_topic)

    # 2) 股票實體偵測（在任何打分之前）
    ent = detect_stock_entity(q)
    q_eff = q
    if not ent and followup and prev_topic == "trade":
        # 「那它的新聞呢？」→ 沿用上一句的股票
        for h in reversed(history or []):
            if h.get("role") == "user":
                e2 = detect_stock_entity(str(h.get("content") or ""))
                if e2:
                    ent, q_eff = e2, f"{e2[1]}{q}"
                    break
    if ent:
        school_sig = hard_school(q)
        if school_sig:
            return _clarify(q, f"你是想問股票的「{ent[1]}」，還是學校的事？", ["trade", "school"], "entity_conflict",
                            f"股票實體 {ent[1]} ＋ {school_sig}", entity=list(ent), followup=followup,
                            prev_topic=prev_topic)
        rem = _remainder_after_entity(q, ent)
        if len(rem) > 5 and not any(w in q for w in TRADE_CONTEXT_WORDS):
            sims = store_sims(q)
            margins = {t: sims[t]["sim"] - _thr_for(thr, t) for t in sims}
            if max(m for t, m in margins.items() if t != "trade") > max(margins["trade"], 0):
                return _clarify(q, f"你是想問股票「{ent[1]}」的狀態，還是一般問題？", ["trade", "general"],
                                "entity_ambiguous", f"股票實體 {ent[1]} 但其餘文字「{rem}」看起來不是在問股票",
                                entity=list(ent), scores=_score_view(sims, thr), followup=followup,
                                prev_topic=prev_topic)
        return Decision(route="trade", stage="entity", reason=f"股票實體 {ent[0]} {ent[1]}", question=q_eff,
                        entity=list(ent), followup=followup, prev_topic=prev_topic)

    # 3) 硬規則
    t_sig, s_sig = hard_trade(q), hard_school(q)
    if t_sig and s_sig:
        return _clarify(q, "你是想問交易／股票的事，還是學校的事？", ["trade", "school"], "hard_conflict",
                        f"{t_sig} ＋ {s_sig}", followup=followup, prev_topic=prev_topic)
    if t_sig:
        return Decision(route="trade", stage="hard_trade", reason=t_sig, question=q, followup=followup,
                        prev_topic=prev_topic)
    if s_sig:
        return Decision(route="school", stage="hard_school", reason=s_sig, question=q, followup=followup,
                        prev_topic=prev_topic)

    # 4) 多層資料庫打分
    sims = store_sims(q)
    topic, why, conf, adj = decide_from_sims(sims, thr, prev_topic, followup)
    view = _score_view(sims, thr, adj)
    if topic == "general" and not followup and is_vague(q):
        return _clarify(q, "想確認一下：你是想問今天的盤勢／帳戶，還是今天的課或學校行程，還是單純聊聊？",
                        ["trade", "school", "general"], "vague", "太短、只有時間詞，沒有主題", scores=view,
                        followup=followup, prev_topic=prev_topic)
    if topic == "clarify":
        if ROUTER_LLM_FALLBACK:
            pick = _llm_topic(q)
            if pick:
                return Decision(route=pick, stage="llm_fallback", reason=f"{why}；LLM 選 {pick}", question=q,
                                scores=view, confidence=0.5, followup=followup, prev_topic=prev_topic)
        top2 = sorted((t for t in adj if t != "general"), key=lambda t: adj[t], reverse=True)[:2]
        if set(top2) == {"trade", "school"}:
            text = "你是想問交易／股票的事，還是學校的事？"
        else:
            text = "你是想問" + "，還是".join(f"「{topic_label(t)}」" for t in top2) + "的事？"
        return _clarify(q, text, top2, "scores", why, scores=view, followup=followup, prev_topic=prev_topic)
    stage = "continuation" if (followup and prev_topic == topic and "延續" in why) else "scores"
    return Decision(route=topic, stage=stage, reason=why, question=q, scores=view, confidence=conf,
                    followup=followup, prev_topic=prev_topic)


def _score_view(sims: dict, thr: dict, adj: dict | None = None) -> dict:
    out = {}
    for t, s in sims.items():
        th = _thr_for(thr, t)
        out[t] = {"store": s["store"], "sim": s["sim"], "thr": th, "margin": round(s["sim"] - th, 4),
                  "best": s["best"], "via": s["via"]}
        if adj is not None:
            out[t]["margin_adj"] = round(adj[t], 4)
    return out
