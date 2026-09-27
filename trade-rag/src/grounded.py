# -*- coding: utf-8 -*-
"""「只根據檢索內容回答」的通用 RAG（grounded answer）。

用在：學校 RAG（scu_answer.ans_rag）與任何「新增資料夾就自動上線」的 store。
Prompt 設計（寫報告可以講）：
  1. 只能用檢索片段 → 降低幻覺
  2. 每個重點附出處〔…〕→ 可驗證
  3. 找不到就回**固定的拒答句** → 程式可以判斷「沒找到」，使用者也不會被編造的內容誤導
  4. 日期守門：答案裡的日期若不在片段中 → 丟棄 LLM 答案，改列原始片段
  5. 簡轉繁：模型飄簡體就用 OpenCC 轉回繁體
"""
from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher

from config import BOT_NAME
from llm import chat
from retrieve import search
from scu_tools import question_clock_hint
from textutil import dates_in, to_traditional

NOT_FOUND = "目前的資料裡沒有找到這項資訊。"


def system_prompt(domain: str, not_found: str = NOT_FOUND) -> str:
    return f"""你是「{BOT_NAME}」，負責回答「{domain}」相關問題，只能根據「檢索到的資料」回答。
規則：
1. 一律使用繁體中文（台灣用語），簡潔回答（最多四句，或一個短列表）。
2. 事件的日期、地點、數字只能照抄檢索資料。系統附上的「現在時間」對照表只用來判斷今天／明天／下週是哪一天，以及哪個事件離現在最近；不可以自己另算一個資料裡沒有的日子。
3. 資料裡沒有答案時，只回答這一句：「{not_found}」；若片段已寫明對應日期或事件，禁止說找不到。禁止自己加總次數（不要寫「2次中秋」這類句子）；不確定有幾次時，改成逐筆列出。
4. 同一件事若有不同學期或年份，先講離「現在時間」最近且還沒結束的那一個，並寫完整年/月/日（不要只寫「11日」）。
5. 遠期（隔年、已結束很久）的項目，除非問題明確問到，否則不要列出來。
6. 每個重點後面用〔〕標出處，例如〔東吳大學行事曆（教務處 ICS）〕。"""


def _hit_date(h: dict) -> date | None:
    raw = str(h.get("date") or h.get("end_date") or "")[:10]
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def rerank(q: str, hits: list[dict], ref_date: date | None = None) -> list[dict]:
    """向量分數＋標題字面重疊＋日期接近現在／問句裡的月日。"""
    asked = dates_in(q)
    for h in hits:
        title = str(h.get("title") or h.get("heading") or "")
        blob = f"{title}\n{h.get('text') or ''}"
        m = SequenceMatcher(None, q, title).find_longest_match(0, len(q), 0, len(title))
        h["lex_bonus"] = min(0.3, 0.075 * m.size) if m.size >= 2 else 0.0
        date_bonus = 0.0
        if asked and dates_in(blob) & asked:
            date_bonus += 0.28
        hd = _hit_date(h)
        if ref_date and hd:
            delta = (hd - ref_date).days
            if delta < -21:
                date_bonus -= 0.16
            elif delta < 0:
                date_bonus += 0.04
            elif delta <= 45:
                date_bonus += 0.18
            elif delta <= 120:
                date_bonus += 0.08
            else:
                date_bonus -= 0.10
        h["date_bonus"] = date_bonus
        h["rank_score"] = float(h.get("faiss_score") or h.get("score") or 0) + h["lex_bonus"] + date_bonus
    return sorted(hits, key=lambda h: h["rank_score"], reverse=True)


_CN_NUM = {"一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_COUNT_RE = re.compile(r"([0-9]+|[一二兩三四五六七八九十])\s*次([\u4e00-\u9fff]{1,8})")


def _bad_counts(text: str, ctx: str) -> list[str]:
    """「2次中秋」這種加總，資料裡那個詞沒有出現那麼多次就視為編造。"""
    bad = []
    for m in _COUNT_RE.finditer(text or ""):
        raw, noun = m.group(1), m.group(2)
        n = _CN_NUM.get(raw, int(raw) if raw.isdigit() else 0)
        if n <= 1:
            continue
        if ctx.count(noun) < n and ctx.count(noun[:2]) < n:
            bad.append(m.group(0))
    return bad


def grounded_answer(q: str, store: str, domain: str, *, context_head: str = "", not_found: str = NOT_FOUND,
                    top_k: int = 6, min_score: float = 0.35, ref_date: date | None = None) -> dict:
    hits = rerank(q, search(q, top_k=12, fetch_k=40, store=store), ref_date=ref_date)[:top_k]
    if not hits or max(float(h.get("rank_score") or 0) for h in hits) < min_score:
        return {"answer": not_found, "sources": [], "hits": hits, "date_guard": "no_hits"}
    ctx = "\n\n".join(f"片段{i}（出處：{h.get('source')}）\n{h.get('text')}" for i, h in enumerate(hits, 1))
    hint = question_clock_hint(q)
    user = f"{context_head}\n{hint}\n問題：{q}\n\n檢索到的資料：\n{ctx}\n\n請只根據上面的資料回答。"
    text = to_traditional(chat([{"role": "system", "content": system_prompt(domain, not_found)},
                                {"role": "user", "content": user}], temperature=0.1, num_predict=400))
    sources = [{"store": store, "type": "faiss", "title": h.get("title") or h.get("heading"),
                "source": h.get("source"), "date": h.get("date"), "url": h.get("url") or None,
                "score": round(float(h.get("rank_score") or 0), 3), "doc_type": h.get("type")} for h in hits]
    allowed = dates_in(ctx) | dates_in(context_head)
    bad = sorted(dates_in(text) - allowed)
    bad_n = _bad_counts(text, ctx)
    guard = "ok"
    if bad or bad_n or not text:
        guard = f"rejected dates={bad} counts={bad_n}"
        lines = ["（模型回答裡的日期或次數對不上資料，改為直接列出最相關的項目）"]
        for h in hits[:4]:
            first = str(h.get("text") or "").split("\n")
            lines.append("• " + " ".join(first[:2]) + f"〔{h.get('source')}〕")
        text = "\n".join(lines)
    return {"answer": text, "sources": sources, "hits": hits, "date_guard": guard}
