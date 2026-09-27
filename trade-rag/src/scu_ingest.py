# -*- coding: utf-8 -*-
"""建立 indexes/scu/（學校知識庫）。

放進向量庫的（沒有固定欄位、適合語意檢索的文字）：
  1. 行事曆事件（去重後）             → type=event
  2. 校園公告標題                      → type=news
  3. 選課時段（依示範學生推算，含是否適用）→ type=window
  4. 政策文字 data/scu/policy.md       → type=policy
不放進向量庫的：3,432 門課程、上課時段、班級課表 → 用 scu_tools.py 的 SQL 精確查詢。

執行：  cd D:\\trade-rag\\src  &&  ..\\.venv\\Scripts\\python.exe scu_ingest.py
（唯讀 scu-backend 的 db.sqlite3；學校資料更新後重跑一次即可）
"""
from __future__ import annotations

import sys
from collections import Counter

from build_store import write_store
from config import SCU_DATA_DIR, SCU_DB, SCU_SEMESTER
from ingest import split_markdown
import scu_tools as T


def event_docs() -> list[dict]:
    out = []
    for e in T.events_all():
        rng = T.fmt_date(e["start_date"])
        iso = e["start_date"]
        if e.get("end_date") and e["end_date"] != e["start_date"]:
            rng += " ～ " + T.fmt_date(e["end_date"])
            iso += " ~ " + e["end_date"]
        src = T.SOURCE_TEXT.get(e["source_name"], e["source_name"])
        text = (f"【行事曆｜{e['category']}】{e['title']}\n日期：{rng}（{iso}）\n學期：{e['semester'] or '—'}\n"
                f"原文：{(e['raw_text'] or '').strip()[:200]}")
        out.append({"source": src, "heading": e["title"], "title": e["title"], "text": text, "type": "event",
                    "category": e["category"], "date": e["start_date"], "end_date": e.get("end_date"),
                    "url": e.get("source_url") or "", "db_table": "events_event", "db_id": e["id"],
                    # 向量用「標題＋分類」比較準（日期數字對語意檢索是雜訊）
                    "embed": f"{e['title']}（{e['category']}）"})
    return out


def news_docs() -> list[dict]:
    out = []
    for n in T.news_latest(limit=10000):
        text = f"【校園公告】{n['title']}\n登刊日期：{T.fmt_date(n['date'])}（{n['date']}）\n發布單位：{n['unit']}｜分類：{n['category']}｜{n['tag']}"
        out.append({"source": "東吳大學校園公告 news.scu.edu.tw", "heading": n["title"][:60], "title": n["title"],
                    "text": text, "type": "news", "date": n["date"], "url": n["url"] or "",
                    "db_table": "events_announcement", "embed": n["title"]})
    return out


def window_docs() -> list[dict]:
    p = T.get_profile()
    out = []
    kind_text = {"select": "可加選也可退選", "drop": "只能退選", "confirm": "只能確認選課清單（不能加退選）"}
    for w in T.selection_windows(p):
        ok = "適用" if w.applies else f"不適用（{w.why_not}）"
        text = (f"【選課時段】{w.title}\n時間：{T.fmt_range(w.start, w.end)}（{w.start:%Y-%m-%d %H:%M} ~ {w.end:%Y-%m-%d %H:%M}）\n"
                f"種類：{kind_text.get(w.kind, w.kind)}；開放範圍：{T.SCOPE_TEXT.get(w.scope, w.scope)}\n"
                f"對 {p['name']}（{p.get('classLabel')}）：{ok}\n學期：{SCU_SEMESTER}")
        out.append({"source": w.source, "heading": w.title, "title": w.title, "text": text, "type": "window",
                    "date": w.start.date().isoformat(), "db_table": "events_event(選課) → windows 推算",
                    "embed": f"選課時段 {w.title}"})
    return out


def policy_docs() -> list[dict]:
    out = []
    for c in split_markdown(SCU_DATA_DIR / "policy.md"):
        c = dict(c)
        c["type"] = "policy"
        c["source"] = "data/scu/policy.md"
        c["embed"] = f"{c['heading']}\n{c['text']}"
        out.append(c)
    return out


def build() -> list[dict]:
    if not SCU_DB.is_file():
        raise SystemExit(f"找不到 scu-backend 資料庫：{SCU_DB}")
    chunks = event_docs() + news_docs() + window_docs() + policy_docs()
    write_store("scu", chunks, embed_field="embed",
                config={"topic": "school", "label": "學校（東吳）", "built_from": str(SCU_DB)})
    print("counts:", dict(Counter(c["type"] for c in chunks)))
    return chunks


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    build()
