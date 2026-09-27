"""個股簡報：持倉／大盤閘門／即時抓個股新聞；可選 Ollama 僅改寫既有事實。"""
from __future__ import annotations

import csv
import json
import re
import urllib.request
from pathlib import Path

from fetch_name_news import fetch_name_news_live
from price_chart import make_price_volume_chart
from live_status import snapshot
from market_status import DISCLAIMER, panel_state

PAPER = Path(r"C:\Users\AUSER\Desktop\trade\snr_backtest\paper")
NAME_NEWS = PAPER / "name_news"
UI_SETTINGS = PAPER / "ui_settings.json"

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:3b"

BRIEF_STATUS_TAIL = "僅狀態描述，非買賣建議。"


def _load_watchlist() -> dict[str, str]:
    watch: dict[str, str] = {}
    if UI_SETTINGS.exists():
        data = json.loads(UI_SETTINGS.read_text(encoding="utf-8"))
        watch.update(data.get("watchlist") or {})
    try:
        account = json.loads((PAPER / "account.json").read_text(encoding="utf-8"))
        for p in account.get("positions") or []:
            t = str(p.get("ticker") or "")
            n = str(p.get("name") or "")
            if t:
                watch.setdefault(t, n)
    except Exception:
        pass
    return watch


def resolve_ticker(q: str) -> tuple[str, str] | None:
    q = q or ""
    watch = _load_watchlist()
    m = re.search(r"\b(\d{4})(?:\.(TW|TWO))?\b", q, re.I)
    if m:
        code = m.group(1)
        suf = (m.group(2) or "").upper()
        candidates = [f"{code}.{suf}"] if suf else [f"{code}.TW", f"{code}.TWO"]
        for c in candidates:
            if c in watch:
                return c, watch[c] or code
        return candidates[0], watch.get(candidates[0], code)
    for t, name in watch.items():
        if name and name in q:
            return t, name
    return None


def _ticker_file_key(ticker: str) -> str:
    return ticker.replace(".", "_")


def latest_name_news(ticker: str) -> dict | None:
    if not NAME_NEWS.exists():
        return None
    key = _ticker_file_key(ticker)
    files = sorted(NAME_NEWS.glob(f"*_{key}.json"))
    if not files:
        code = ticker.split(".")[0]
        files = sorted(NAME_NEWS.glob(f"*{code}*.json"))
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding="utf-8"))


def latest_size_row(ticker: str) -> dict | None:
    path = PAPER / "size_journal.csv"
    if not path.exists():
        return None
    hit = None
    with path.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if (r.get("ticker") or "") == ticker:
                hit = r
    return hit


def _collect_holding(ticker: str) -> str:
    try:
        account = json.loads((PAPER / "account.json").read_text(encoding="utf-8"))
        for p in account.get("positions") or []:
            if p.get("ticker") == ticker:
                return (
                    f"持有 {p.get('shares')} 股，成本約 {p.get('avg_price')}，"
                    f"進場日 {p.get('entry_date')}"
                )
        return "未持有"
    except Exception as e:
        return f"持倉讀取失敗：{e}"


def _collect_gate() -> str:
    st = panel_state() or {}
    if st.get("trend") is not None or st.get("size_weight") is not None:
        w = float(st.get("size_weight") or 0)
        cash = float(st.get("cash") or 0)
        gate = f"大盤 trend={st.get('trend')}，預算池 {w:.0%}≈{cash * w:,.0f} 元；"
        if st.get("lock_new"):
            gate += "硬關（不能新開）"
        else:
            gate += "可新開（詳見面板／news_risk）"
        if st.get("reason"):
            gate += f"｜{st.get('reason')}"
        return gate
    try:
        s = snapshot()
        gate = (
            f"大盤 trend={s.get('trend')}，預算池 {s.get('size_weight', 0):.0%}≈"
            f"{s.get('pool', 0):,.0f} 元；"
        )
        if s.get("lock_new"):
            gate += "硬關（不能新開）"
        elif s.get("soft_cap"):
            gate += f"軟關（最多新開 {s.get('max_new_entries')} 檔）"
        else:
            gate += "未設軟上限"
        return gate
    except Exception as e:
        return f"大盤閘門讀取失敗：{e}"


def _headline_snip(nn: dict | None, n: int = 3) -> list[str]:
    if not nn:
        return []
    titles = (nn.get("off_headlines") or [])[:3] + (nn.get("on_headlines") or [])[:2]
    if not titles:
        titles = (nn.get("sample_titles") or [])[:n]
    return [str(t) for t in titles[:n]]


def build_raw_facts(
    ticker: str,
    name: str,
    held: str,
    gate: str,
    nn: dict | None,
    fetch_note: str,
    sj: dict | None,
) -> str:
    if nn:
        news_line = (
            f"個股新聞快取 {nn.get('session')}：score={nn.get('news_score')} "
            f"trend={nn.get('trend')} lock={nn.get('lock')}（更新 {nn.get('updated_at')}）"
            f"{fetch_note}"
        )
        titles = _headline_snip(nn, 5)
        title_lines = "\n".join(f"  - {t}" for t in titles) or "  （無標題）"
        news_block = news_line + "\n近期標題（含來源名；目前無獨立 URL）：\n" + title_lines
    else:
        news_block = "個股新聞快取：尚無資料。" + fetch_note

    if sj:
        size_line = (
            f"size_journal 最近：name_heat={sj.get('name_heat')} "
            f"name_trend={sj.get('name_trend')} name_lock={sj.get('name_lock')} "
            f"target_weight={sj.get('target_weight')} note={sj.get('note')}"
        )
    else:
        size_line = "size_journal：無此檔紀錄。"

    return "\n".join(
        [
            f"【個股簡報】{ticker} {name}",
            f"持倉：{held}",
            f"大盤閘門：{gate}",
            size_line,
            news_block,
            DISCLAIMER,
        ]
    )


def structured_short_brief(
    ticker: str,
    name: str,
    held: str,
    gate: str,
    nn: dict | None,
    sj: dict | None,
) -> str:
    """Tight Traditional Chinese block from provided facts only (no LLM)."""
    lines = [
        f"【摘要】{ticker} {name}",
        f"• 持倉：{held}",
        f"• 閘門：{gate}",
    ]
    if sj:
        lines.append(
            f"• 個股熱度：heat={sj.get('name_heat')} trend={sj.get('name_trend')} "
            f"lock={sj.get('name_lock')}"
        )
    if nn:
        lines.append(
            f"• 新聞：score={nn.get('news_score')} trend={nn.get('trend')} "
            f"lock={nn.get('lock')}（{nn.get('session')}）"
        )
        for t in _headline_snip(nn, 2):
            lines.append(f"  - {t}")
    else:
        lines.append("• 新聞：無可用快取")
    lines.append(BRIEF_STATUS_TAIL)
    return "\n".join(lines)


def _ollama_rephrase(facts_blob: str) -> str | None:
    """Optional local rephrase; must not invent numbers or advice."""
    system = (
        "你是紙上交易狀態摘要器。只用使用者提供的事實改寫成繁體中文。"
        "最多三句短句。禁止發明數字、標題、建議買賣、預測漲跌。"
        "若事實不足就照實說「資料不足」。"
        f"最後一句必須是：{BRIEF_STATUS_TAIL}"
    )
    user = (
        "請把下列事實改寫成最多三句繁中摘要（可含簡短條列，但仍總計約三句內）：\n\n"
        f"{facts_blob}"
    )
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "keep_alive": 0,
        "options": {"temperature": 0.1},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = (data.get("message") or {}).get("content") or ""
        text = text.strip()
        if not text:
            return None
        if BRIEF_STATUS_TAIL not in text:
            text = text.rstrip("。") + "。" + BRIEF_STATUS_TAIL
        return text
    except Exception:
        return None




def looks_like_stock_brief_intent(q: str) -> bool:
    """Bare '個股簡報' (also typo 各股) without needing a ticker name."""
    q = (q or "").strip()
    if not q:
        return False
    keys = ("個股簡報", "各股簡報", "持股簡報", "持倉簡報", "持股狀態", "持倉狀態")
    return any(k in q for k in keys)


def list_holding_tickers() -> list[tuple[str, str]]:
    """Current paper positions as (ticker, name), stable order."""
    out: list[tuple[str, str]] = []
    try:
        account = json.loads((PAPER / "account.json").read_text(encoding="utf-8"))
        for p in account.get("positions") or []:
            t = str(p.get("ticker") or "")
            n = str(p.get("name") or "")
            if t:
                out.append((t, n or t))
    except Exception:
        pass
    return out


def format_holdings_briefs() -> str:
    rows = list_holding_tickers()
    if not rows:
        return "目前 paper 帳戶沒有持倉，無法產個股簡報。請點名股票（例如：世紀今天的狀態）。"
    parts = [f"【持倉個股簡報】共 {len(rows)} 檔（只讀狀態，非買賣建議）"]
    for t, name in rows:
        try:
            parts.append(format_stock_brief(t, name))
        except Exception as e:
            parts.append(f"【{t} {name}】簡報失敗：{e}")
    return "\n\n————\n\n".join(parts)

def format_stock_brief(ticker: str, name: str) -> str:
    held = _collect_holding(ticker)
    gate = _collect_gate()

    fetch_note = ""
    nn = None
    try:
        # live fetch writes UTF-8 cache; always read back from disk (stdout may be cp950)
        fetch_name_news_live(ticker, name)
        nn = latest_name_news(ticker)
        fetch_note = "（已即時向原程式請求抓取）"
    except Exception as e:
        fetch_note = f"（即時抓取失敗，改用舊快取：{e}）"
        nn = latest_name_news(ticker)

    sj = latest_size_row(ticker)
    raw = build_raw_facts(ticker, name, held, gate, nn, fetch_note, sj)
    short = structured_short_brief(ticker, name, held, gate, nn, sj)

    # Optional LLM polish over the structured facts only; fall back to structured.
    polished = _ollama_rephrase(short)
    summary = polished if polished else short

    chart = make_price_volume_chart(ticker, name)
    if chart.get("ok") and chart.get("url"):
        chart_line = (
            f"價量圖（近60日，只讀）：收盤 {chart.get('last_close')} @ {chart.get('last_date')}\n"
            f"[[chart:{chart['url']}]]"
        )
    else:
        chart_line = f"價量圖：無法產生（{chart.get('error')}）"

    return "\n\n".join(
        [
            summary,
            chart_line,
            "——",
            "【原始事實】",
            raw,
        ]
    )
