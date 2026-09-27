# -*- coding: utf-8 -*-
"""全功能聊天機器人的入口：router 決定主題 → 交給對應的處理器 → 統一回傳格式。

    chat(message, history=None, profile=None, mode=None) -> {
        answer, route, sub_route, sources[], decision{stage, reason, scores, confidence, ...},
        clarify?, latency_ms, model
    }
UI（chat_ui.py 的 /ask、/api/chat）與評測（eval/run_eval.py）都呼叫這一支。
"""
from __future__ import annotations

import json
import threading
import time
import traceback
from datetime import datetime

from config import CHAT_MODEL, LOG_DIR, ROUTE_LOG
from router import route

_log_lock = threading.Lock()


def _trade(q: str) -> dict:
    from answer import ask

    res = ask(q)
    sources = [{"store": h.get("store", "trade"), "type": "faiss" if res.get("mode") == "rules" else "live",
                "title": f"{h.get('source')} / {h.get('heading')}", "source": h.get("source"),
                "score": round(float(h.get("score") or 0), 3)} for h in res.get("hits", [])[:5]]
    return {"answer": res.get("answer", ""), "sources": sources, "trade_mode": res.get("mode"),
            "hits": res.get("hits", []), "model": CHAT_MODEL}


def write_log(rec: dict) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with _log_lock, ROUTE_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def _parse_now(value) -> datetime | None:
    if not value:
        return None
    from scu_tools import TZ

    try:
        d = datetime.fromisoformat(str(value).strip().replace(" ", "T"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=TZ)


def chat(message: str, history: list[dict] | None = None, profile: dict | None = None,
         mode: str | None = None, source: str = "api", now=None, facts: str | None = None,
         followup: bool = False) -> dict:
    t0 = time.perf_counter()
    message = (message or "").strip()
    from scu_tools import reset_request_now, set_request_now

    token = set_request_now(_parse_now(now))
    try:
        return _chat(message, history, profile, mode, source, facts, t0, followup)
    finally:
        reset_request_now(token)


def _chat(message: str, history, profile, mode, source, facts, t0, followup: bool = False) -> dict:
    from scu_tools import clock_question_answer

    if mode == "portal":
        from general_chat import speak_facts
        from router import Decision

        d = Decision(route="portal", sub="facts", stage="portal", reason="入口站已給站內事實，只改寫", question=message)
        t_route = time.perf_counter()
        out: dict = {"route": "portal", "sub_route": "facts", "sources": [], "clarify": None, "model": CHAT_MODEL}
        try:
            text = speak_facts(message, facts or "", history, followup=followup)
            out["answer"] = text or (facts or "（模型沒有回應，請再試一次）")
        except Exception as e:
            out["answer"] = facts or f"處理時發生錯誤：{e}"
            out["error"] = traceback.format_exc()[-800:]
        t1 = time.perf_counter()
        out["latency_ms"] = {"route": round((t_route - t0) * 1000), "total": round((t1 - t0) * 1000)}
        out["decision"] = {k: v for k, v in d.to_json().items() if k not in ("route", "sub", "clarify")}
        write_log({"ts": datetime.now().isoformat(timespec="seconds"), "source": source, "message": message,
                   "route": out["route"], "sub": out["sub_route"], "stage": d.stage, "reason": d.reason,
                   "scores": {}, "prev_topic": None, "followup": False, "latency_ms": out["latency_ms"],
                   "error": bool(out.get("error"))})
        return out

    clock_ans = None if mode else clock_question_answer(message)
    d = route(message, history, mode)
    t_route = time.perf_counter()
    out: dict = {"route": d.route, "sub_route": d.sub, "sources": [], "clarify": None, "model": None}
    try:
        if clock_ans:
            out["route"] = "general"
            out["sub_route"] = "clock"
            out["answer"] = clock_ans
            d.route, d.sub, d.stage, d.reason = "general", "clock", "clock", "純時間問題，用系統時鐘，不經模型"
        elif d.route == "clarify":
            out["answer"] = d.clarify["question"]
            out["clarify"] = d.clarify
        elif d.route == "trade":
            r = _trade(d.question)
            out.update(answer=r["answer"], sources=r["sources"], model=r["model"], trade_mode=r["trade_mode"])
        elif d.route == "school":
            from scu_answer import answer as school_answer

            r = school_answer(d.question, history, profile, sub=d.sub, params=d.params)
            out.update(answer=r["answer"], sources=r["sources"], model=r.get("model"), sub_route=r["sub"])
            if r.get("date_guard"):
                out["date_guard"] = r["date_guard"]
        elif d.route == "general":
            from general_chat import reply

            r = reply(message, history)
            out.update(answer=r["answer"], sources=[], model=r["model"])
        else:
            # 自動發現的新 store（新增資料夾即可）：通用 grounded RAG
            from grounded import grounded_answer
            from router import topic_label, topic_stores

            store = topic_stores().get(d.route, d.route)
            r = grounded_answer(d.question, store, topic_label(d.route))
            out.update(answer=r["answer"], sources=r["sources"], model=CHAT_MODEL, date_guard=r["date_guard"])
    except Exception as e:
        out["answer"] = f"處理時發生錯誤：{e}"
        out["error"] = traceback.format_exc()[-800:]
    t1 = time.perf_counter()
    out["latency_ms"] = {"route": round((t_route - t0) * 1000), "total": round((t1 - t0) * 1000)}
    out["decision"] = {k: v for k, v in d.to_json().items() if k not in ("route", "sub", "clarify")}
    write_log({"ts": datetime.now().isoformat(timespec="seconds"), "source": source, "message": message,
               "route": out["route"], "sub": out["sub_route"], "stage": d.stage, "reason": d.reason,
               "scores": {t: {"sim": s["sim"], "thr": s["thr"], "margin": s["margin"]} for t, s in d.scores.items()},
               "prev_topic": d.prev_topic, "followup": d.followup, "latency_ms": out["latency_ms"],
               "error": bool(out.get("error"))})
    return out
