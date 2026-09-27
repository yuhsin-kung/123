"""路由：規則 RAG／今日帳戶／個股簡報／加權／夜盤／三大法人。"""
from __future__ import annotations

import json
import sys
import urllib.request

from live_status import format_brief, looks_like_live_question, snapshot
from market_status import (
    format_institutional,
    format_market_bundle,
    format_twii,
    format_txf_night,
)
from retrieve import search
from stock_brief import (
    format_holdings_briefs,
    format_stock_brief,
    looks_like_stock_brief_intent,
    resolve_ticker,
)

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen2.5:3b"

SYSTEM = """你是「交易規則手冊」助教，只根據檢索片段回答。

硬性限制：
1. 繁體中文；整段答案最多三句。
2. 只寫直接相關的結論，不要堆條件、不要複述多個片段。
3. 每句關鍵結論後加出處：[檔名 / 小節名]。
4. 片段沒寫到就說「規則未載明」，禁止腦補。
5. 不進場／不成交／減碼等字眼必須跟片段一致。
6. 普通關稅／升溫＝減碼或縮池，不是硬關。
"""


def build_context(hits: list[dict]) -> str:
    ordered = sorted(
        hits,
        key=lambda h: (0 if "規則" in str(h.get("heading", "")) else 1, -float(h.get("score", 0))),
    )
    blocks = []
    for i, h in enumerate(ordered, 1):
        blocks.append(
            f"片段{i}\n檔名: {h['source']}\n小節: {h['heading']}\n內容:\n{h['text']}"
        )
    return "\n\n".join(blocks)


def _clock_brief() -> str:
    from scu_tools import clock_brief

    return clock_brief()


def ask_rules(question: str, top_k: int = 5) -> dict:
    # 只查 trade store：新增 scu/general store 之後，不能讓學校資料混進交易規則答案
    hits = search(question, top_k=top_k, store="trade")
    if not hits or max(float(h.get("score") or 0) for h in hits) < 0.35:
        return {"question": question, "answer": "規則未載明。", "hits": hits, "mode": "rules"}
    context = build_context(hits)
    user = (
        f"問題：{question}\n\n"
        f"以下是檢索到的片段（可能含無關內容，請自行取捨）：\n{context}\n\n"
        "請用最多三句回答，並在關鍵結論後加上 [檔名 / 小節]。不要展開無關條件。"
    )
    payload = {
        "model": MODEL,
        "stream": False,
        "keep_alive": 0,
        "options": {"temperature": 0.1},
        "messages": [
            {"role": "system", "content": SYSTEM + "\n\n" + _clock_brief()},
            {"role": "user", "content": user},
        ],
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    answer = data.get("message", {}).get("content", "")
    return {"question": question, "answer": answer, "hits": hits, "mode": "rules"}


def _wrap(mode: str, question: str, text: str, source: str) -> dict:
    return {
        "question": question,
        "answer": text,
        "hits": [{"source": source, "heading": mode, "text": text, "score": 1.0}],
        "mode": mode,
    }


def looks_like_inst(q: str) -> bool:
    keys = ("三大法人", "外資", "投信", "自營", "買賣超", "法人")
    return any(k in q for k in keys)


def looks_like_twii(q: str) -> bool:
    keys = ("加權", "TWII", "大盤指數", "台股指數", "加權指數")
    return any(k in q for k in keys)


def looks_like_night(q: str) -> bool:
    keys = ("夜盤", "台指期", "TX", "期貨盤後")
    return any(k in q for k in keys)


def trade_subroute(question: str) -> tuple[str, tuple[str, str] | None]:
    """交易主題內的子路徑判斷（與原本 ask() 的 if 順序完全相同，只是抽出來）。

    回傳 (sub, resolved)：
      holdings_brief  「個股簡報」但沒點名 → 全部持倉簡報
      stock_brief     點名某檔（名稱或代號）→ 個股簡報＋價量圖
      institutional / txf_night / twii / live / rules
    抽出來的好處：路由評測可以只「判斷」不「執行」（不會真的去抓新聞）。
    """
    q = question or ""
    # bare 個股/各股簡報 → all holdings (before rules RAG)
    if looks_like_stock_brief_intent(q) and resolve_ticker(q) is None:
        return "holdings_brief", None
    resolved = resolve_ticker(q)
    # stock brief if named stock and not pure rule % question
    if resolved and not (q.strip().endswith("％") or q.strip().endswith("%") or "規則" in q):
        return "stock_brief", resolved
    if looks_like_inst(q):
        return "institutional", None
    if looks_like_night(q):
        return "txf_night", None
    if looks_like_twii(q):
        return "twii", None
    if looks_like_live_question(q):
        return "live", None
    return "rules", None


def ask(question: str, top_k: int = 5) -> dict:
    q = question or ""
    sub, resolved = trade_subroute(q)
    if sub == "holdings_brief":
        return _wrap("stock", q, format_holdings_briefs(), "paper/name_news+account")
    if sub == "stock_brief":
        # if asking 建議買X - still stock brief (status only)
        t, name = resolved
        return _wrap("stock", q, format_stock_brief(t, name), "paper/name_news+account")
    if sub == "institutional":
        return _wrap("institutional", q, format_institutional(), "paper/institutional.json")
    if sub == "txf_night":
        return _wrap("txf_night", q, format_txf_night(), "panel/txf_night")
    if sub == "twii":
        return _wrap("twii", q, format_twii(), "panel/twii|TWII.csv")
    if sub == "live":
        try:
            brief = format_brief(snapshot())
            # append short market strip
            extra = "\n\n" + format_twii() + "\n\n" + format_institutional()
            return _wrap("live", q, brief + extra, "paper+market")
        except Exception as e:
            return _wrap("live_error", q, f"讀取紙上狀態失敗（只讀）：{e}", "error")
    return ask_rules(q, top_k=top_k)


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "今天三大法人怎麼看？"
    result = ask(q)
    print("mode:", result.get("mode"))
    print("Q:", result["question"])
    print("\nA:", result["answer"])
