# -*- coding: utf-8 -*-
"""呼叫本機 Ollama 的小工具（標準庫 urllib，不需額外套件）。"""
from __future__ import annotations

import json
import urllib.request

from config import CHAT_MODEL, KEEP_ALIVE, OLLAMA_URL


def _with_clock(messages: list[dict]) -> list[dict]:
    """每次生成都附上同一套時鐘。分類器（只要一個單字）不要附，避免它改口報日期。"""
    from scu_tools import clock_brief

    brief = clock_brief()
    out = [dict(m) for m in messages]
    if out and out[0].get("role") == "system":
        out[0]["content"] = str(out[0].get("content") or "").rstrip() + "\n\n" + brief
    else:
        out.insert(0, {"role": "system", "content": brief})
    return out


def chat(messages: list[dict], *, temperature: float = 0.3, model: str | None = None,
         keep_alive=KEEP_ALIVE, timeout: int = 180, num_predict: int | None = None,
         with_clock: bool = True) -> str:
    options = {"temperature": temperature}
    if num_predict:
        options["num_predict"] = num_predict
    payload = {"model": model or CHAT_MODEL, "stream": False, "keep_alive": keep_alive,
               "options": options, "messages": _with_clock(messages) if with_clock else messages}
    req = urllib.request.Request(OLLAMA_URL, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return ((data.get("message") or {}).get("content") or "").strip()
