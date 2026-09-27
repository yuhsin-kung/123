"""events/services.py — 把 Event / Announcement 整理成前端 js/real-events.js 的格式

移植自 scu-events/export_frontend.py（同樣的去重、route、id 規則），所以
GET /api/events 的內容 = window.SCU_REAL_EVENTS，GET /api/news = window.SCU_REAL_NEWS。
"""
import hashlib
import re
from datetime import date, timedelta

from django.utils import timezone

from .models import Announcement, Event

TYPE_OF = Event.FRONT_TYPE
SOURCE_LABEL = {
    "scu_calendar_ics": "東吳大學行事曆（教務處 Google 日曆）",
    "scu_calendar_pdf": "115學年度行事曆 PDF（註冊課務組）",
    "scu_course_timetable": "學士班網路選課註冊時間表 PDF（註冊課務組）",
    "announcement_title": "校園公告標題",
}


def sha1(*parts):
    return hashlib.sha1("|".join("" if p is None else str(p) for p in parts).encode("utf-8")).hexdigest()


def academic_year_window(roc_year):
    y = roc_year + 1911
    return date(y, 8, 1), date(y + 1, 7, 31)


def route_for(cat, title):
    if cat == "選課":
        return "#/p/final-drop" if "退修" in title else "#/course"
    if cat == "繳費":
        return "#/p/loan" if ("貸款" in title or "就貸" in title) else "#/p/fee"
    if cat == "獎助學金":
        return "#/p/scholarship"
    if cat == "考試":
        return "#/timetable"
    return "#/calendar"


def _norm(t):
    return re.sub(r"[\s。，,、()（）:：]", "", t)


def front_events(year=115, since=None, include_staff=False):
    lo, hi = academic_year_window(year)
    since = since or (lo - timedelta(days=61))

    def rows(src):
        return list(Event.objects.filter(source_name=src, is_active=True, start_date__gte=since,
                                         start_date__lte=hi).order_by("start_date", "id"))

    cal, cal_src = rows("scu_calendar_ics"), "scu_calendar_ics"
    if not cal:                                   # ICS 抓不到時退回 PDF
        cal, cal_src = rows("scu_calendar_pdf"), "scu_calendar_pdf"
    extra = rows("scu_course_timetable") + [r for r in rows("announcement_title") if r.category != "公告"]
    out, seen = [], set()
    for r in cal + extra:
        if r.audience == "staff" and not include_staff:
            continue
        if r.source_name == "scu_course_timetable" and r.title.startswith("上課開始"):
            continue
        key = (r.start_date, r.end_date, _norm(r.title))
        if key in seen:
            continue
        seen.add(key)
        desc = ([r.note] if r.note else []) + ["來源：" + SOURCE_LABEL.get(r.source_name, r.source_name)]
        ev = {"id": "scu-" + sha1(r.source_name, r.uid)[:10], "start": r.start_date.isoformat(),
              "type": TYPE_OF.get(r.category, "school"), "title": r.title, "desc": "。".join(desc),
              "route": route_for(r.category, r.title), "category": r.category, "semester": r.semester,
              "audience": r.audience, "source": r.source_name, "sourceUrl": r.source_url, "raw": r.raw_text}
        if r.end_date:
            ev["end"] = r.end_date.isoformat()
        out.append(ev)
    out.sort(key=lambda e: (e["start"], e.get("end") or e["start"]))
    return out, cal_src, since


def front_news(limit=60):
    """日期新到舊；同一天依公告編號大到小（同 export_frontend.py）"""
    from django.db.models import IntegerField
    from django.db.models.functions import Cast
    qs = Announcement.objects.annotate(nid=Cast("news_id", IntegerField())).order_by("-date", "-nid", "-id")
    return [a.to_front() for a in qs[:limit]]


def front_meta(events, news, cal_src, since):
    counts = {}
    for e in events:
        counts[e["category"]] = counts.get(e["category"], 0) + 1
    last = Event.objects.order_by("-fetched_at").values_list("fetched_at", flat=True).first()
    return {"generatedAt": timezone.localtime(last).isoformat(timespec="seconds") if last else "",
            "calendarSource": cal_src, "since": since.isoformat(), "counts": counts,
            "nEvents": len(events), "nNews": len(news),
            "sources": {"calendar_ics": "https://calendar.google.com/calendar/ical/3k064p6cntvj0e9d31uobbdstg%40group.calendar.google.com/public/basic.ics",
                        "calendar_page": "https://web-ch.scu.edu.tw/regcurr/web_page/2288",
                        "news": "https://news.scu.edu.tw/news"},
            "disclaimer": "資料擷取自東吳大學公開網頁，實際日期以學校公告為準。"}
