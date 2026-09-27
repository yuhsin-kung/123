# -*- coding: utf-8 -*-
"""學校主題（SCU）的回答：先判斷子意圖，再決定用「SQL 工具」還是「向量檢索＋LLM」。

  子意圖            作法                               為什麼
  profile          SQL（accounts_studentprofile）      固定欄位
  course_lookup    SQL（課名精確比對）                  要完整、正確的老師／教室／時間
  selection_window SQL＋規則（移植 windows.py）          時間判斷是規則，不是語意
  my_timetable     SQL（enrollment＋coursesession）     精確篩選：星期＝3
  class_timetable  SQL（classcourse＋coursesession）    精確篩選：班級＝資科三B
  news             SQL（依日期排序）                    「最新」是排序問題，不是相似度問題
  events_upcoming  SQL（日期 >= 今天）                  「下一次」是日期比較
  rag              FAISS（indexes/scu）＋ LLM            自由問法：「期末退修什麼時候？」
結構化答案直接用資料排版，不經 LLM → 不會編造日期。RAG 答案再加一道「日期守門」。
"""
from __future__ import annotations

import re
from datetime import date
import scu_tools as T
from config import CHAT_MODEL
from grounded import grounded_answer

NOT_FOUND = "目前的學校資料裡沒有找到這項資訊。"

PROFILE_RE = re.compile(r"(我是誰|我的(學號|系所|科系|班級|年級|資料|個人資料)|我幾年級|我讀什麼系|我是哪一?班)")
SELECT_RE = re.compile(r"(選課|加退選|加選|退選|初選|確認選課清單|選課清單)")
TIMETABLE_RE = re.compile(r"(有什麼課|有哪些課|有課|沒課|什麼課|哪些課|課表|第\s*[0-9一二三四五六七八九EA-D]{1,2}\s*節|幾點上課|要上課|上什麼)")
DAY_WORD_RE = re.compile(r"(今天|今日|明天|明日|後天|昨天|等一下|等等|待會|現在|星期[一二三四五六日天]|週[一二三四五六日]|周[一二三四五六日]|禮拜[一二三四五六日天])")
NEWS_RE = re.compile(r"(公告|最新消息|校園消息|學校消息|新聞)")
COURSE_LOOKUP_RE = re.compile(r"(誰教|老師|教授|教室|學分|上課時間|哪天|星期幾|幾點|選課編號|在哪|哪裡上|哪間)")
UPCOMING_RE = re.compile(r"(下一個|下一次|下次|接下來|最近的|快到|還有多久|下個|即將)")
HOLIDAY_RE = re.compile(r"(放假|假期|連假|補假|補班|放什麼假)")
CALENDAR_OVERVIEW_RE = re.compile(r"(行事曆|校曆)")
SPECIFIC_EVENT_RE = re.compile(r"(退修|期中|期末考|期末|選課|繳費|註冊|開學|畢業|加退選)")
HOLIDAY_NAMES = ("教師節", "國慶", "中秋", "春節", "元旦", "開國", "端午", "清明", "勞動", "行憲",
                 "校慶", "寒假", "暑假", "調整放假", "學術交流週")
# 長詞在前，避免「期末考」先吃掉「期末考試」
CALENDAR_EVENT_NAMES = HOLIDAY_NAMES + ("期中考試", "期末考試", "期末退修", "期中考", "期末考", "退修",
                                         "開學日", "畢業典禮")
CATEGORY_WORDS = {"考試": ("考試", "期中", "期末考", "英檢", "補考", "考"), "放假": ("放假", "假期", "連假", "放什麼假", "假日"),
                  "繳費": ("繳費", "學雜費", "學費"), "選課": ("選課",)}
NEWS_TOPICS = {"獎學金": ("獎學金", "獎助", "助學金", "補助"), "講座": ("講座", "演講"), "活動": ("活動",),
               "徵才": ("徵才", "工讀", "實習", "職缺"), "考試": ("考試", "英檢"), "繳費": ("繳費",),
               "網路": ("網路",), "宿舍": ("宿舍",), "交換": ("交換", "出國", "研習")}


# ---------------------------------------------------------------------------
# 子意圖判斷（路由器也會呼叫，評測時只判斷不執行）
# ---------------------------------------------------------------------------
def _prev_user(history: list[dict] | None) -> str:
    for h in reversed(history or []):
        if h.get("role") == "user" and str(h.get("content") or "").strip():
            return str(h["content"])
    return ""


def school_subroute(q: str, history: list[dict] | None = None, _depth: int = 0) -> tuple[str, dict]:
    q = q or ""
    params: dict = {}
    cls = T.find_class_label(q)
    if cls:
        params["class_label"] = cls
    names = T.find_course_names(q)
    if PROFILE_RE.search(q):
        return "profile", params
    if names and not cls and not TIMETABLE_RE.search(q):
        params["course_names"] = names
        return "course_lookup", params
    if SELECT_RE.search(q) and "退修" not in q:
        return "selection_window", params
    has_day = bool(DAY_WORD_RE.search(q))
    if TIMETABLE_RE.search(q) or (has_day and "課" in q) or (cls and ("課" in q or has_day)):
        return ("class_timetable" if cls else "my_timetable"), params
    if NEWS_RE.search(q):
        return "news", params
    if history and _depth == 0 and re.search(r"為何|為什麼|為甚麼", q):
        prev = _prev_user(history)
        if prev and prev.strip() != q.strip():
            sub, params = school_subroute(prev, None, _depth + 1)
            params["explain_count"] = True
            return sub, params
    if re.search(r"幾次|多少次|多少個|幾個", q) and re.search(r"假|放", q):
        return "holiday_tally", params
    named = next((n for n in CALENDAR_EVENT_NAMES if n in q), None)
    day, _, day_txt = T.find_day(q, T.now())
    if HOLIDAY_RE.search(q) or named:
        if day:
            params["date"] = day.isoformat()
            params["day_txt"] = day_txt
        if named:
            params["keyword"] = named
        return "holiday", params
    if UPCOMING_RE.search(q):
        for cat, words in CATEGORY_WORDS.items():
            if any(w in q for w in words):
                params["category"] = cat
                return "events_upcoming", params
    if CALENDAR_OVERVIEW_RE.search(q) and not SPECIFIC_EVENT_RE.search(q):
        return "events_upcoming", params
    # 追問：「那星期四呢？」沿用上一題的子意圖（與班級）
    if _depth == 0 and history and has_day:
        prev = _prev_user(history)
        if prev:
            psub, pparams = school_subroute(prev, None, _depth=1)
            if psub in ("class_timetable", "my_timetable"):
                if "class_label" in pparams and "class_label" not in params:
                    params["class_label"] = pparams["class_label"]
                params["inherited_from"] = prev
                return ("class_timetable" if params.get("class_label") else "my_timetable"), params
    return "rag", params


# ---------------------------------------------------------------------------
# 各子意圖的回答
# ---------------------------------------------------------------------------
def _src(kind: str, title: str, **kw) -> dict:
    d = {"store": "scu", "type": kind, "title": title}
    d.update({k: v for k, v in kw.items() if v not in (None, "")})
    return d


def ans_profile(p: dict) -> dict:
    text = (f"預設學生資料：{p['name']}（學號 {p.get('student_id')}），{p['program']} {p['dept']} "
            f"{p['grade']} 年級 {p['cls']} 班（{p.get('classLabel') or '班級未找到'}），{p.get('college', '')}。")
    return {"answer": text, "sources": [_src("sqlite", "accounts_studentprofile / config.DEFAULT_PROFILE")]}


def ans_timetable(q: str, p: dict, params: dict, sub: str) -> dict:
    ref = T.now()
    d, wd, day_txt = T.find_day(q, ref)
    if sub == "class_timetable":
        label = params["class_label"]
        slots, what = T.class_slots(label), f"{label} 班級課表"
        src = _src("sqlite", f"{label} 班級課表", table="timetable_classcourse + timetable_coursesession")
    else:
        slots, what = T.my_slots(p)
        src = _src("sqlite", what, table="enrollment_enrollment + timetable_coursesession")
    if not slots:
        return {"answer": f"找不到{what}的資料。" + NOT_FOUND, "sources": [src]}
    lines: list[str] = []
    if wd:
        n = T.week_no(d) if d else None
        head = f"{what}｜{day_txt}"
        if d:
            head += f"（{d.month}/{d.day} 星期{T.WD[wd - 1]}"
            head += f"，第 {n} 週）" if n else "）"
        lines.append(head)
        if d:
            hol = T.holidays_on(d)
            if hol:
                lines.append(f"⚠ 這天行事曆是「{hol[0]['title']}」，照行事曆應該不用上課。以下是平常這天的課：")
        day_slots = T.sort_slots([s for s in slots if s.weekday == wd])
        shown = 0
        for s in day_slots:
            ok = T.week_type_applies(s.week_type, n)
            if ok is False:
                lines.append(f"• （本週不上）{T.fmt_slot(s)}")
                continue
            tag = ""
            if d and d == ref.date() and s.start and s.end:
                hm = f"{ref:%H:%M}"
                tag = "【上課中】" if s.start <= hm < s.end else ("【已結束】" if s.end <= hm else "")
            lines.append(f"• {tag}{T.fmt_slot(s)}")
            shown += 1
        if not day_slots:
            lines.append("這天沒有排課。")
        elif shown == 0:
            lines.append("這天的課本週都不上（單雙週）。")
    else:
        lines.append(f"{what}（整週）")
        for s in T.sort_slots(slots):
            lines.append(f"• {T.fmt_slot(s, with_day=True)}")
    lines.append(f"（資料：scu-backend 資料庫，{T.SCU_SEMESTER} 學期；{T.now_phrase()} {ref:%Y/%m/%d %H:%M}）")
    return {"answer": "\n".join(lines), "sources": [src]}


def ans_course_lookup(p: dict, params: dict) -> dict:
    lines, sources = [], []
    mine = p.get("classLabel")
    for name in params.get("course_names", []):
        offs = T.course_offerings(name)
        if not offs:
            continue
        by_course: dict = {}
        for s in offs:
            by_course.setdefault((s.code or s.cid, s.offering_class), []).append(s)
        items = sorted(by_course.items(), key=lambda kv: (kv[0][1] != mine, kv[0][1]))
        lines.append(f"「{name}」共 {len(items)} 個開課班：")
        for (code, ocls), ss in items[:6]:
            s0 = ss[0]
            times = "；".join(T.fmt_slot(s, with_day=True).split(" " + s.name)[0] for s in T.sort_slots(ss))
            me = "（你的班）" if ocls == mine else ""
            lines.append(f"• {ocls}{me}｜{s0.teacher or '教師未定'}｜{s0.credits:g} 學分｜選課編號 {code}｜{times}"
                         + (f"｜教室 {', '.join(sorted({s.room for s in ss if s.room}))}" if any(s.room for s in ss) else ""))
        if len(items) > 6:
            lines.append(f"…另有 {len(items) - 6} 班未列出")
        sources.append(_src("sqlite", f"課程「{name}」", table="timetable_course + timetable_coursesession"))
    if not lines:
        return {"answer": NOT_FOUND, "sources": []}
    return {"answer": "\n".join(lines), "sources": sources}


def ans_selection(p: dict) -> dict:
    ref = T.now()
    st = T.window_status(p, ref)
    lines = [st["reason"]]
    if st["confirm_now"]:
        pass
    elif st["confirm_next"]:
        w = st["confirm_next"][0]
        lines.append(f"接下來：「{w.title}」{T.fmt_range(w.start, w.end)}（只能確認選課清單，不能加退選）。")
    lines.append(f"本學期（{T.SCU_SEMESTER}）適用你的選課時段：")
    for w in st["windows"]:
        if not w.applies:
            continue
        status = "進行中" if w.start <= ref < w.end else ("未開始" if ref < w.start else "已結束")
        kind = {"select": "加退選", "drop": "只能退選", "confirm": "確認清單"}.get(w.kind, w.kind)
        lines.append(f"• {w.title}｜{T.fmt_range(w.start, w.end)}｜{kind}｜{status}")
    src = _src("sqlite", "學士班網路選課註冊時間表 → 選課時段推算", table="events_event (category=選課)")
    return {"answer": "\n".join(lines), "sources": [src]}


def ans_news(q: str) -> dict:
    kws = []
    for words in NEWS_TOPICS.values():
        if any(w in q for w in words):
            kws.extend(words)
    rows = T.news_latest(limit=5, keywords=kws or None)
    if not rows:
        return {"answer": "目前的公告資料裡沒有找到相關公告。", "sources": [_src("sqlite", "校園公告", table="events_announcement")]}
    head = "相關公告（依日期新到舊）：" if kws else "最新校園公告（依登刊日期新到舊）："
    lines = [head] + [f"• {r['date']}｜{r['unit']}｜{r['title']}" for r in rows]
    srcs = [_src("sqlite", r["title"][:40], table="events_announcement", url=r["url"], date=r["date"]) for r in rows]
    return {"answer": "\n".join(lines), "sources": srcs}


def ans_upcoming(params: dict) -> dict:
    ref = T.now()
    cat = params.get("category")
    if cat:
        rows = T.events_upcoming(ref, category=cat, limit=4)
    else:
        seen, rows = set(), []
        for kind, n in (("選課", 2), ("放假", 2), ("考試", 2)):
            for e in T.events_upcoming(ref, category=kind, limit=n):
                k = (e["title"], e["start_date"])
                if k in seen:
                    continue
                seen.add(k)
                rows.append(e)
        rows.sort(key=lambda e: (e["start_date"], e["id"]))
        rows = rows[:6]
    label = f"「{cat}」" if cat else "項目"
    if not rows:
        return {"answer": f"行事曆裡沒有找到 {ref:%Y/%m/%d} 之後的{label}。", "sources": []}
    lines = [f"從{T.now_phrase()} {ref:%Y/%m/%d} 起，行事曆上接下來的{label}："]
    lines += [f"• {T.fmt_event(e)}〔{T.SOURCE_TEXT.get(e['source_name'], e['source_name'])}〕" for e in rows]
    srcs = [_src("sqlite", e["title"], table="events_event", date=e["start_date"], url=e.get("source_url")) for e in rows]
    return {"answer": "\n".join(lines), "sources": srcs}


def _semester_holidays() -> list[dict]:
    """115-1 上課期間的放假（不含寒暑假整段）。"""
    start, end = "2026-08-01", "2027-02-01"
    out = []
    for e in T.events_all():
        if e.get("category") != "放假":
            continue
        if not (start <= e["start_date"] < end):
            continue
        if any(w in (e.get("title") or "") for w in ("寒假", "暑假")):
            continue
        out.append(e)
    return out


def ans_holiday_tally(params: dict) -> dict:
    rows = _semester_holidays()
    if not rows:
        return {"answer": "這學期的行事曆裡沒有列出國定放假。", "sources": []}
    lines = [f"這學期行事曆裡的放假一共 {len(rows)} 筆（一筆算一次，不會把同一個日子算兩次）："]
    for e in rows:
        lines.append(f"• {T.fmt_event(e)}〔{T.SOURCE_TEXT.get(e['source_name'], e['source_name'])}〕")
    srcs = [_src("sqlite", e["title"], table="events_event", date=e["start_date"], url=e.get("source_url")) for e in rows]
    return {"answer": "\n".join(lines), "sources": srcs}


def ans_holiday(params: dict) -> dict:
    """放假／節日用 SQL 對日期，不經 LLM（避免 10/9 被向量檢索對成端午節）。"""
    ref = T.now()
    raw_d = params.get("date")
    d = date.fromisoformat(raw_d) if raw_d else None
    kw = params.get("keyword")
    lines, sources = [], []
    if d:
        hol = T.holidays_on(d)
        if hol:
            lines.append(f"{T.fmt_date(d.isoformat())} 行事曆有放假：")
            for e in hol:
                lines.append(f"• {T.fmt_event(e)}〔{T.SOURCE_TEXT.get(e['source_name'], e['source_name'])}〕")
                sources.append(_src("sqlite", e["title"], table="events_event", date=e["start_date"],
                                    url=e.get("source_url")))
        else:
            lines.append(f"{T.fmt_date(d.isoformat())} 行事曆沒有放假紀錄。")
            sources.append(_src("sqlite", f"{d.isoformat()} 放假", table="events_event"))
    if kw:
        rows = T.events_search(kw, ref, limit=3)
        if rows:
            if lines:
                lines.append("")
            head = f"行事曆裡與「{kw}」有關的項目共 {len(rows)} 筆"
            if params.get("explain_count"):
                head += "。資料只有這些，沒有第二次"
            lines.append(head + "：")
            for e in rows:
                lines.append(f"• {T.fmt_event(e)}〔{T.SOURCE_TEXT.get(e['source_name'], e['source_name'])}〕")
                sources.append(_src("sqlite", e["title"], table="events_event", date=e["start_date"],
                                    url=e.get("source_url")))
        elif not d:
            return {"answer": f"行事曆裡沒有找到「{kw}」相關項目。", "sources": []}
    if not lines:
        rows = T.events_upcoming(ref, category="放假", limit=4)
        if not rows:
            return {"answer": f"從 {ref:%Y/%m/%d} 起，行事曆沒有列出接下來的放假。", "sources": []}
        lines = [f"從{T.now_phrase()} {ref:%Y/%m/%d} 起，接下來的放假："]
        for e in rows:
            lines.append(f"• {T.fmt_event(e)}〔{T.SOURCE_TEXT.get(e['source_name'], e['source_name'])}〕")
            sources.append(_src("sqlite", e["title"], table="events_event", date=e["start_date"],
                                url=e.get("source_url")))
    return {"answer": "\n".join(lines), "sources": sources}


# ---------------------------------------------------------------------------
# RAG（向量檢索 indexes/scu）＋ LLM ＋ 日期守門（共用 grounded.py）
# ---------------------------------------------------------------------------
def ans_rag(q: str, p: dict) -> dict:
    ref = T.now()
    head = (f"現在時間：{ref:%Y/%m/%d %H:%M}（星期{T.WD[ref.weekday()]}）\n"
            f"學生：{p['name']}，{p['dept']} {p.get('classLabel') or ''}")
    return grounded_answer(q, "scu", "東吳大學校園事務（行事曆、公告、選課）", context_head=head,
                           not_found=NOT_FOUND, ref_date=ref.date())


def answer(q: str, history: list[dict] | None = None, profile: dict | None = None,
           sub: str | None = None, params: dict | None = None) -> dict:
    p = T.get_profile(profile)
    if sub is None:
        sub, params = school_subroute(q, history)
    params = params or {}
    if sub == "profile":
        out = ans_profile(p)
    elif sub in ("my_timetable", "class_timetable"):
        qq = q
        out = ans_timetable(qq, p, params, sub)
    elif sub == "course_lookup":
        out = ans_course_lookup(p, params)
    elif sub == "selection_window":
        out = ans_selection(p)
    elif sub == "news":
        out = ans_news(q)
    elif sub == "events_upcoming":
        out = ans_upcoming(params)
    elif sub == "holiday":
        out = ans_holiday(params)
    elif sub == "holiday_tally":
        out = ans_holiday_tally(params)
    else:
        sub = "rag"
        out = ans_rag(q, p)
    out["sub"] = sub
    out["model"] = CHAT_MODEL if sub == "rag" else None
    out["profile"] = {k: v for k, v in p.items() if not k.startswith("_")}
    return out
