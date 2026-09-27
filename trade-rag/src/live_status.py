"""只讀 Desktop\\trade 的紙上帳戶／新聞風險，組出「今天大概能開多少」摘要。

不寫入、不下單。路徑若缺失就清楚說明。
"""
from __future__ import annotations

import json
from pathlib import Path

PAPER_DIR = Path(r"C:\Users\AUSER\Desktop\trade\snr_backtest\paper")
ACCOUNT_PATH = PAPER_DIR / "account.json"
NEWS_PATH = PAPER_DIR / "news_risk.json"


def _load(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot() -> dict:
    account = _load(ACCOUNT_PATH)
    news = _load(NEWS_PATH)
    cash = float(account.get("cash") or 0)
    equity = float(account.get("equity") or 0)
    positions = account.get("positions") or []
    weight = float(news.get("size_weight") or 0)
    pool = cash * weight
    lock_new = bool(news.get("lock_new"))
    soft_cap = bool(news.get("soft_cap"))
    max_new = news.get("max_new_entries")
    trend = news.get("trend")
    return {
        "cash": cash,
        "equity": equity,
        "n_positions": len(positions),
        "positions": [
            f"{p.get('ticker')} {p.get('name')} {p.get('shares')}股"
            for p in positions
        ],
        "session": news.get("session"),
        "updated_at": news.get("updated_at"),
        "trend": trend,
        "news_score": news.get("news_score"),
        "size_weight": weight,
        "pool": pool,
        "lock_new": lock_new,
        "soft_cap": soft_cap,
        "max_new_entries": max_new,
        "red_day": news.get("red_day"),
        "price_pause": news.get("price_pause"),
        "war_lock": news.get("war_lock"),
        "reason": news.get("reason"),
        "account_updated_at": account.get("updated_at"),
    }


def format_brief(s: dict | None = None) -> str:
    s = s or snapshot()
    lines = [
        f"資料日：新聞 {s['session']}（{s['updated_at']}），帳戶 {s['account_updated_at']}",
        f"現金約 {s['cash']:,.0f} 元；權益約 {s['equity']:,.0f} 元；目前持股 {s['n_positions']} 檔。",
        f"今日熱度 trend={s['trend']}（score={s['news_score']}），預算池比例 {s['size_weight']:.0%} → 今日新倉預算池約 {s['pool']:,.0f} 元。",
    ]
    if s["lock_new"]:
        lines.append("閘門：硬關，今日不能新開倉。")
    elif s["soft_cap"] and s["max_new_entries"] is not None:
        lines.append(f"閘門：軟關，今日新開最多 {s['max_new_entries']} 檔（預算池內再分配）。")
    elif s["max_new_entries"] is not None:
        lines.append(f"閘門：新開上限 {s['max_new_entries']} 檔。")
    else:
        lines.append("閘門：未設檔數軟上限（仍受預算池與單檔 20% 限制）。")
    if s["positions"]:
        lines.append("現有部位：" + "；".join(s["positions"]))
    if s.get("reason"):
        lines.append("系統原由：" + str(s["reason"]))
    lines.append("（只讀摘要，非下單指令；細節仍以 RULE 手冊＋原紙上程式為準。）")
    return "\n".join(lines)


# 必須像在問「此刻狀態」，不要把純規則題（例如 severe 是多少％）搶走
LIVE_MUST = ("今天", "今日", "現在", "此刻", "目前")
LIVE_ACTION = ("能開", "可以開", "開多少", "還能買", "多少倉", "持倉", "部位", "我的現金", "帳戶")


def looks_like_live_question(q: str) -> bool:
    q = q or ""
    if any(k in q for k in LIVE_MUST):
        return True
    return any(k in q for k in LIVE_ACTION)


if __name__ == "__main__":
    print(format_brief())
