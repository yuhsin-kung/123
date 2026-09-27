# -*- coding: utf-8 -*-
"""建立路由器需要的小索引：
  indexes/general/index.faiss   一般聊天主題樣本（general store 的內容）
  indexes/trade/anchors.faiss   交易主題錨點問句（不動 trade 的 index.faiss）
  indexes/scu/anchors.faiss     學校主題錨點問句

執行：  ..\\.venv\\Scripts\\python.exe build_router.py
"""
from __future__ import annotations

import sys

from build_store import write_anchors, write_store
from config import GENERAL_DATA_DIR, ROUTER_DIR


def _lines(path) -> list[str]:
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.lstrip().startswith("#")]


def build() -> None:
    topics = _lines(GENERAL_DATA_DIR / "topics.txt")
    write_store("general", [{"source": "data/general/topics.txt", "heading": t, "title": t, "text": t,
                             "type": "topic"} for t in topics],
                config={"topic": "general", "label": "一般聊天", "note": "只給路由器打分用，不做檢索回答"})
    for store in ("trade", "scu"):
        write_anchors(store, _lines(ROUTER_DIR / f"anchors_{store}.txt"))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    build()
