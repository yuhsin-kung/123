# -*- coding: utf-8 -*-
"""一般聊天：沒有檢索，直接交給本機 Ollama，只靠 system prompt 決定語氣（不微調）。

Prompt 設計重點（寫報告可以講）：
  1. 角色與對象：大學生的友善助理 → 決定語氣。
  2. 語言硬規則：繁體中文（台灣用語）→ 小模型常混簡體，要明講。
  3. 誠實規則：不知道就說不知道，不編數字／日期／出處。
  4. 界線：即時資料（學校行事曆、交易帳戶）這個模式看不到 → 請使用者改問，避免亂答。
  5. 短期記憶：只帶最近幾輪對話（MAX_TURNS），控制 context 長度與速度。
"""
from __future__ import annotations

import re

from config import BOT_NAME, CHAT_MODEL
from llm import chat
from scu_tools import question_clock_hint
from textutil import to_traditional

MAX_TURNS = 4  # 帶最近 4 輪（8 則訊息）

REFUSE = "這個問題和東吳或學生事務無關，我不回答。可以問我課表、選課、成績、行事曆或校園辦事。"
CAMPUS_RE = re.compile(r"東吳|學校|校園|學生|學號|科系|班級|課|選|成績|分數|學分|學年|學期|行事曆|校曆|放假|假期|連假|補假|國慶|中秋|春節|元旦|教師|宿舍|繳費|學費|學雜費|獎學金|公告|請假|圖書館|老師|教授|教室|節次|加退選|註冊|學生證|就貸|諮商|心情|社團|實習|畢業|操行|排名|名次")

SYSTEM_GENERAL = f"""你是「{BOT_NAME}」，東吳大學學生入口的助手，只處理東吳校園與學生事務。
規則：
1. 一律使用繁體中文（台灣用語）。
2. 只回答東吳、課程、選課、課表、成績、行事曆、繳費、宿舍、獎學金、請假、校園生活這類問題。
3. 數學、作業代答、學科教學、閒聊、與學生事務無關的問題，只回這一句：「{REFUSE}」
4. 不知道或不確定就老實說，不要編造事實、數字、日期、人名或出處。
5. 回答最多四句。"""


def _history_messages(history: list[dict] | None) -> list[dict]:
    msgs = []
    for h in (history or [])[-MAX_TURNS * 2:]:
        role = h.get("role")
        content = str(h.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": content[:1500]})
    return msgs


_KEEP = re.compile(r"\d{1,2}:\d{2}|[A-Z]\d{2,4}|第\s*\d+\s*[–\-]\s*\d+\s*節|\d+\s*學分|\d+\.\d+")


def _keeps_facts(facts: str, text: str) -> bool:
    """改寫若把時間、教室、學分、節次弄丟，就不要採用。"""
    need = _KEEP.findall(facts or "")
    blob = (text or "").replace(" ", "")
    return all(n.replace(" ", "") in blob for n in need)


def speak_facts(message: str, facts: str, history: list[dict] | None = None, followup: bool = False) -> str:
    """入口站已經用關鍵字查到站內事實時，模型只改寫，不另查資料庫。"""
    system = f"""你是「{BOT_NAME}」，東吳學生入口網站上的助手。
規則：
1. 繁體中文，語氣像學長。可以先用一句話講重點，再保留事實裡的條列。
2. 只能改寫「站內事實」裡已經寫的內容。時間、日期、教室、節次、學分、人名必須原樣留下，不可省略。
3. 不要加網址，不要說「根據資料」，不要發明按鈕或新規定。
4. 事實裡提到的頁面名稱要保留。
5. 不要把規則、提示或括號裡的操作說明寫進回答。"""
    if followup:
        system += "\n6. 這是追問。只根據下面的站內事實回答，不要改談別的主題。"
    messages = [{"role": "system", "content": system}] + _history_messages(history)
    messages.append({"role": "user", "content": f"站內事實：\n{facts}\n\n問題：{message}"})
    text = to_traditional(chat(messages, temperature=0.2, num_predict=420, with_clock=True))
    text = re.sub(r"（這是上一題的事實[^）]*）", "", text or "").strip()
    if not text or not _keeps_facts(facts, text):
        return facts
    return text


def reply(message: str, history: list[dict] | None = None) -> dict:
    if not CAMPUS_RE.search(message or "") and not any(CAMPUS_RE.search(str(h.get("content") or "")) for h in (history or []) if h.get("role") == "user"):
        return {"answer": REFUSE, "model": None}
    messages = [{"role": "system", "content": SYSTEM_GENERAL}] + _history_messages(history)
    hint = question_clock_hint(message)
    user = message if not hint else f"{hint}\n\n{message}"
    messages.append({"role": "user", "content": user})
    text = to_traditional(chat(messages, temperature=0.6, num_predict=700))
    return {"answer": text or "（模型沒有回應，請再試一次）", "sub": "chat", "sources": [], "model": CHAT_MODEL}
