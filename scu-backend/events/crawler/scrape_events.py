#!/usr/bin/env python3
"""scrape_events.py - pull Soochow University (東吳大學) public school-wide
dates into SQLite (scu_events.db). Safe to run frequently (upsert + dedupe).

Sources (all public, no login):
  ics       東吳大學行事曆 public Google Calendar ICS  (PRIMARY 行事曆 source)
            embedded on https://web-ch.scu.edu.tw/regcurr/web_page/2288
  pdf       115學年度行事曆 PDF (教務處註冊課務組, attached to news/166768)
            -> parsed with poppler `pdftotext -layout`, used to cross-check ICS
  timetable 學士班網路選課註冊時間表 PDF (www.scu.edu.tw/regcurr/courseselection/universitytimetable.pdf)
            -> 選課階段 / 繳費 / 就學貸款 / 助學金 rows, `pdftotext -raw`
  news      https://news.scu.edu.tw/news  校園公告 list (title/date/category/unit)
  units     unit news lists on web-ch.scu.edu.tw (德育中心 最新消息, 註冊課務組 課程及選課)

Usage:
  python scrape_events.py                         # everything, default settings
  python scrape_events.py --only ics,news         # subset
  python scrape_events.py --news-pages 10         # deeper backfill of announcements
  python scrape_events.py --news-detail-limit 20  # fetch detail pages of NEW items for 資料提供 unit
  python scrape_events.py --year 115              # academic year window (ROC)

Politeness: >=1.5s between requests, descriptive UA, stops the whole run on 403/429.
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

import scu_common as C

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "scu_events.db")

ICS_CAL_ID = "3k064p6cntvj0e9d31uobbdstg@group.calendar.google.com"
ICS_URL = ("https://calendar.google.com/calendar/ical/"
           "3k064p6cntvj0e9d31uobbdstg%40group.calendar.google.com/public/basic.ics")
ICS_PAGE = "https://web-ch.scu.edu.tw/regcurr/web_page/2288"
# news post that carries the 115 學年度行事曆 PDF attachment (update yearly)
CAL_PDF_NEWS = {115: "https://news.scu.edu.tw/news/166768"}
TIMETABLE_PDF = "https://www.scu.edu.tw/regcurr/courseselection/universitytimetable.pdf"
NEWS_LIST = "https://news.scu.edu.tw/news"
UNIT_LISTS = [
    # (source_name, unit, url)
    ("unit_life", "德育中心", "https://web-ch.scu.edu.tw/life/opinion/2427"),
    # ("unit_regcurr_course", "註冊課務組", "https://web-ch.scu.edu.tw/regcurr/opinion/2301"),  # stale (last post 2023)
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  uid         TEXT NOT NULL,             -- stable per-source key (ICS UID, or hash of raw row)
  title       TEXT NOT NULL,
  category    TEXT NOT NULL,             -- 選課/繳費/考試/放假/獎助學金/學校/公告
  start_date  TEXT NOT NULL,             -- YYYY-MM-DD (Asia/Taipei)
  end_date    TEXT,                      -- YYYY-MM-DD inclusive; NULL = single day
  source_name TEXT NOT NULL,
  source_url  TEXT,
  fetched_at  TEXT NOT NULL,
  raw_text    TEXT,
  hash        TEXT NOT NULL,             -- content hash (title|start|end|category) for change detection
  semester    TEXT,                      -- e.g. 115-1
  audience    TEXT DEFAULT 'student',    -- student / staff
  note        TEXT,                      -- parser warnings (e.g. date conflict)
  first_seen  TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  is_active   INTEGER NOT NULL DEFAULT 1,-- 0 = disappeared from source on a later run
  UNIQUE (source_name, uid)
);
CREATE INDEX IF NOT EXISTS ix_events_start ON events(start_date);
CREATE INDEX IF NOT EXISTS ix_events_hash ON events(hash);

CREATE TABLE IF NOT EXISTS announcements (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  source_name TEXT NOT NULL,             -- news / unit_life / ...
  news_id     TEXT NOT NULL,             -- news.scu.edu.tw id, or hash for unit lists (no permalink)
  title       TEXT NOT NULL,
  date        TEXT,                      -- 登刊日期 YYYY-MM-DD
  unit        TEXT,                      -- 發布單位 (from 【...】 prefix or 資料提供)
  category    TEXT,                      -- site category (一般公告/學生活動/...)
  tag         TEXT,                      -- our keyword category (選課/繳費/獎助學金/...)
  url         TEXT,
  fetched_at  TEXT NOT NULL,
  first_seen  TEXT NOT NULL,
  hash        TEXT NOT NULL,
  UNIQUE (source_name, news_id)
);
CREATE INDEX IF NOT EXISTS ix_ann_date ON announcements(date);

CREATE TABLE IF NOT EXISTS crawl_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_name TEXT, started_at TEXT, finished_at TEXT,
  status TEXT, n_items INTEGER, message TEXT
);
"""


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def db_connect(path=DB_PATH):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def upsert_events(con, source_name, events, fetched_at, window=None):
    """events: list of dicts with uid,title,category,start_date,end_date,source_url,raw_text,
    semester,audience,note. Returns (inserted, updated, unchanged, deactivated)."""
    ins = upd = same = 0
    seen = set()
    for e in events:
        h = C.sha1(e["title"], e["start_date"], e.get("end_date"), e["category"], e.get("note"), e.get("semester"), e.get("audience"))
        seen.add(e["uid"])
        row = con.execute("SELECT id, hash FROM events WHERE source_name=? AND uid=?",
                          (source_name, e["uid"])).fetchone()
        if row is None:
            con.execute("""INSERT INTO events (uid,title,category,start_date,end_date,source_name,source_url,
                           fetched_at,raw_text,hash,semester,audience,note,first_seen,updated_at,is_active)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                        (e["uid"], e["title"], e["category"], e["start_date"], e.get("end_date"), source_name,
                         e.get("source_url"), fetched_at, e.get("raw_text"), h, e.get("semester"),
                         e.get("audience", "student"), e.get("note"), fetched_at, fetched_at))
            ins += 1
        elif row["hash"] != h:
            con.execute("""UPDATE events SET title=?,category=?,start_date=?,end_date=?,source_url=?,fetched_at=?,
                           raw_text=?,hash=?,semester=?,audience=?,note=?,updated_at=?,is_active=1 WHERE id=?""",
                        (e["title"], e["category"], e["start_date"], e.get("end_date"), e.get("source_url"),
                         fetched_at, e.get("raw_text"), h, e.get("semester"), e.get("audience", "student"),
                         e.get("note"), fetched_at, row["id"]))
            upd += 1
        else:
            con.execute("UPDATE events SET fetched_at=?, is_active=1 WHERE id=?", (fetched_at, row["id"]))
            same += 1
    deact = 0
    if window is not None:  # anything in the window that vanished from the source -> inactive
        lo, hi = window
        rows = con.execute("SELECT id, uid FROM events WHERE source_name=? AND is_active=1 "
                           "AND start_date BETWEEN ? AND ?", (source_name, lo.isoformat(), hi.isoformat())).fetchall()
        for r in rows:
            if r["uid"] not in seen:
                con.execute("UPDATE events SET is_active=0, updated_at=? WHERE id=?", (fetched_at, r["id"]))
                deact += 1
    con.commit()
    return ins, upd, same, deact


def upsert_announcements(con, items, fetched_at):
    new = 0
    for a in items:
        h = C.sha1(a["title"], a.get("date"), a.get("unit"), a.get("category"))
        row = con.execute("SELECT id, hash FROM announcements WHERE source_name=? AND news_id=?",
                          (a["source_name"], a["news_id"])).fetchone()
        if row is None:
            con.execute("""INSERT INTO announcements (source_name,news_id,title,date,unit,category,tag,url,
                           fetched_at,first_seen,hash) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (a["source_name"], a["news_id"], a["title"], a.get("date"), a.get("unit"),
                         a.get("category"), a.get("tag"), a.get("url"), fetched_at, fetched_at, h))
            new += 1
        else:
            con.execute("""UPDATE announcements SET title=?,date=?,unit=COALESCE(?,unit),category=?,tag=?,url=?,
                           fetched_at=?,hash=? WHERE id=?""",
                        (a["title"], a.get("date"), a.get("unit"), a.get("category"), a.get("tag"), a.get("url"),
                         fetched_at, h, row["id"]))
    con.commit()
    return new


def log_crawl(con, source, started, status, n, msg=""):
    con.execute("INSERT INTO crawl_log (source_name,started_at,finished_at,status,n_items,message) "
                "VALUES (?,?,?,?,?,?)", (source, started, C.now_iso(), status, n, msg[:2000]))
    con.commit()


def make_event(uid, summary, start, end, source_url, note=None, default_cat="學校", title_prefix=""):
    title, *_ = C.clean_title(summary)
    if not title:
        title = summary.strip()
    return {
        "uid": uid,
        "title": title_prefix + title,
        "category": C.categorize(title, default_cat),
        "start_date": start.isoformat(),
        "end_date": end.isoformat() if end and end != start else None,
        "source_url": source_url,
        "raw_text": summary.strip(),
        "semester": C.semester_of(start),
        "audience": C.audience_of(title),
        "note": note,
    }


# ---------------------------------------------------------------------------
# 1) ICS (primary 行事曆)
# ---------------------------------------------------------------------------
def parse_ics(text):
    lines = text.replace("\r\n", "\n").split("\n")
    unfolded = []
    for ln in lines:
        if ln.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += ln[1:]
        else:
            unfolded.append(ln)
    events, cur = [], None
    for ln in unfolded:
        if ln == "BEGIN:VEVENT":
            cur = {}
        elif ln == "END:VEVENT":
            if cur is not None:
                events.append(cur)
            cur = None
        elif cur is not None and ":" in ln:
            k, v = ln.split(":", 1)
            name, *params = k.split(";")
            v = v.replace("\\,", ",").replace("\\;", ";").replace("\\n", "\n").replace("\\\\", "\\")
            cur[name] = (v, params)
    return events


def ics_date(value, params, is_end=False):
    """Return a local (Asia/Taipei) date. DATE-valued DTEND is exclusive."""
    if "VALUE=DATE" in params or re.fullmatch(r"\d{8}", value):
        d = datetime.strptime(value[:8], "%Y%m%d").date()
        return d - timedelta(days=1) if is_end else d
    if value.endswith("Z"):
        dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=C.timezone.utc).astimezone(C.TZ)
    else:
        dt = datetime.strptime(value[:15], "%Y%m%dT%H%M%S").replace(tzinfo=C.TZ)
    if is_end:
        dt -= timedelta(seconds=1)
    return dt.date()


def title_date_check(summary, start, end):
    """SCU titles start with the day ('17日...', '15~24日...'); warn if it disagrees with the calendar date."""
    _, d1, m2, d2 = C.clean_title(summary)
    probs = []
    in_range = d1 is not None and end and start <= start.replace(day=1) + timedelta(days=d1 - 1) <= end
    if d1 is not None and d1 != start.day and not in_range:
        probs.append(f"標題寫 {d1} 日，但行事曆日期為 {start.isoformat()}")
    if d2 is not None and end and d2 != end.day:
        probs.append(f"標題結束日寫 {d2} 日，但行事曆結束日為 {end.isoformat()}")
    return "；".join(probs) or None


def scrape_ics(sess, year):
    lo, hi = C.academic_year_window(year)
    text = sess.get(ICS_URL).content.decode("utf-8")
    raw = parse_ics(text)
    out = []
    for ev in raw:
        if ev.get("STATUS", ("",))[0] == "CANCELLED" or "DTSTART" not in ev:
            continue
        s = ics_date(*ev["DTSTART"])
        e = ics_date(*ev["DTEND"], is_end=True) if "DTEND" in ev else s
        if e < s:
            e = s
        if not (lo <= s <= hi):
            continue
        summary = ev.get("SUMMARY", ("",))[0]
        note = title_date_check(summary, s, e)
        if "RRULE" in ev:
            note = ((note + "；") if note else "") + "重複事件，只存第一次"
        out.append(make_event(ev["UID"][0], summary, s, e, ICS_PAGE, note))
    return out, (lo, hi)


# ---------------------------------------------------------------------------
# 2) 行事曆 PDF (cross-check)
# ---------------------------------------------------------------------------
PDF_EVENT_RE = re.compile(
    r"(?P<d1>\d{1,2})\s*(?:日\s*)?(?:[~～]\s*(?:(?P<m2>\d{1,2})\s*月\s*)?(?P<d2>\d{1,2})\s*)?日\s*(?P<text>\S.*)$")


def pdftotext(pdf_bytes, mode="-layout", first=None, last=None):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        path = f.name
    try:
        cmd = ["pdftotext", mode, "-enc", "UTF-8"]
        if first:
            cmd += ["-f", str(first)]
        if last:
            cmd += ["-l", str(last)]
        return subprocess.run(cmd + [path, "-"], capture_output=True, check=True).stdout.decode("utf-8")
    finally:
        os.unlink(path)


def pdf_pages(pdf_bytes):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        path = f.name
    try:
        info = subprocess.run(["pdfinfo", path], capture_output=True, check=True).stdout.decode("utf-8", "replace")
        return int(re.search(r"Pages:\s+(\d+)", info).group(1))
    finally:
        os.unlink(path)


def find_calendar_pdf_url(sess, year):
    page = CAL_PDF_NEWS.get(year)
    if not page:
        return None
    s = BeautifulSoup(sess.get(page).text, "lxml")
    for a in s.find_all("a", href=True):
        if a["href"].lower().endswith(".pdf") and "行事曆" in a.get_text():
            return urljoin(page, a["href"])
    return None


def parse_calendar_pdf_text(text, year, source_url):
    y = C.roc_to_ad(year)
    out = []
    sem = None
    month = last_day = None
    for ln in text.splitlines():
        if "學年度第一學期行事曆" in ln.replace(" ", ""):
            sem, month, last_day = 1, 8, 0
            continue
        if "學年度第二學期行事曆" in ln.replace(" ", ""):
            sem, month, last_day = 2, 2, 0
            continue
        if sem is None or ln.strip().startswith("註："):
            continue
        m = PDF_EVENT_RE.search(ln)
        if not m:
            continue
        d1 = int(m.group("d1"))
        if d1 < last_day:  # day went backwards -> next month
            month = month % 12 + 1
        last_day = d1
        yy = y + 1 if (sem == 2 or month < 8) else y
        start = date(yy, month, d1)
        end = start
        if m.group("d2"):
            m2 = int(m.group("m2")) if m.group("m2") else month
            ey = yy + 1 if m2 < month else yy
            end = date(ey, m2, int(m.group("d2")))
        raw = ln[m.start():].strip()
        summary = raw
        out.append(make_event(C.sha1("pdf", year, sem, raw), summary, start, end, source_url))
    return out


def scrape_calendar_pdf(sess, year):
    url = find_calendar_pdf_url(sess, year)
    if not url:
        raise RuntimeError("calendar PDF link not found")
    pdf = sess.get(url).content
    return parse_calendar_pdf_text(pdftotext(pdf), year, url)


# ---------------------------------------------------------------------------
# 3) 選課註冊時間表 PDF (學士班)
# ---------------------------------------------------------------------------
MONTH_LABEL = {"六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12, "一": 1, "二": 2}
TT_START_RE = re.compile(r"^(?:(?P<m1>\d{1,2})\s*月\s*)?(?P<d1>\d{1,2})\s*日(?P<rest>.*)$")
TT_END_RE = re.compile(r"^(?:(?P<m2>\d{1,2})\s*月\s*)?(?P<d2>\d{1,2})\s*日(?:止)?\s*(?P<rest>.*)$")
TIME_RE = re.compile(r"^\d{1,2}\s*[:：]\s*\d{2}$")


def parse_timetable_pdf(pdf_bytes, source_url):
    first_page = pdftotext(pdf_bytes, "-raw", 1, 1)
    m = re.search(r"(\d{3})\s*學年度第\s*(\d)\s*學期", first_page)
    if not m:
        raise RuntimeError("timetable: cannot find 學年度/學期 header")
    roc, sem = int(m.group(1)), int(m.group(2))
    base_year = C.roc_to_ad(roc) if sem == 1 else C.roc_to_ad(roc) + 1
    out = []
    month = None
    last_day = 0
    for page in range(1, pdf_pages(pdf_bytes) + 1):
        lines = [l.strip() for l in pdftotext(pdf_bytes, "-raw", page, page).splitlines() if l.strip()]
        labels = [MONTH_LABEL[l] for l in lines if l in MONTH_LABEL]
        if not labels and month is None:
            continue
        if labels and (month is None or lines.index(next(l for l in lines if l in MONTH_LABEL)) > 0):
            # items above the first month label on a page belong to that label's month
            month, last_day = labels[0], 0
        i = 0
        while i < len(lines):
            ln = lines[i]
            if ln in MONTH_LABEL:
                if MONTH_LABEL[ln] != month:
                    month, last_day = MONTH_LABEL[ln], 0
                i += 1
                continue
            if ln.startswith(("導師輔導選課說明", "選課說明", "註冊說明")):
                break  # explanatory prose follows; stop this page
            sm = TT_START_RE.match(ln)
            if not sm or month is None:
                i += 1
                continue
            m1 = int(sm.group("m1")) if sm.group("m1") else None
            d1 = int(sm.group("d1"))
            rest = sm.group("rest").strip()
            if m1 is None:
                if d1 < last_day:
                    month = month % 12 + 1
                last_day = d1
            smonth = m1 or month
            times, end_m, end_d, title = [], None, None, ""
            # same-line forms: "~ 7 月 2 日", "~30 日止", "9:00~19:00 xxx", "(含)前", "起 xxx"
            j = i + 1
            def take_end(txt):
                em = TT_END_RE.match(txt)
                return (int(em.group("m2")) if em.group("m2") else None, int(em.group("d2")), em.group("rest").strip()) if em else None
            r = rest
            tm = re.match(r"^(\d{1,2}\s*[:：]\s*\d{2}\s*[~～]\s*\d{1,2}\s*[:：]\s*\d{2})\s*(.*)$", r)
            if tm:
                times.append(tm.group(1)); r = tm.group(2)
            if r.startswith(("~", "～")):
                te = take_end(r[1:].strip())
                if te:
                    end_m, end_d, r = te
            r = re.sub(r"^(?:\(含\)|（含）)?\s*(?:前|起|止)\s*", lambda mm: "", r)
            tm2 = re.match(r"^(\d{1,2}\s*[:：]\s*\d{2})\s*起?\s*(.*)$", r)
            if tm2:
                times.append(tm2.group(1)); r = tm2.group(2)
            title = r.strip()
            # multi-line form: time / ~ / end day / time / title
            while j < len(lines) and not title:
                nx = lines[j]
                if TIME_RE.match(nx):
                    times.append(nx); j += 1; continue
                if nx in ("~", "～"):
                    j += 1
                    if j < len(lines):
                        te = take_end(lines[j])
                        if te:
                            end_m, end_d, rr = te
                            j += 1
                            if rr:
                                title = rr
                    continue
                if nx in MONTH_LABEL:
                    # a month label between the date and its title (seen in raw mode)
                    if MONTH_LABEL[nx] != month:
                        month = MONTH_LABEL[nx]
                    j += 1; continue
                if TT_START_RE.match(nx):
                    break
                title = nx; j += 1
            i = max(j, i + 1)
            if not title:
                continue
            # "開學後加退選○" + next line "1 ：學系專業課程"  ->  "開學後加退選①：學系專業課程"
            if title.endswith("○") and i < len(lines):
                sm2 = re.match(r"^(\d)\s*[:：]\s*(.+)$", lines[i])
                if sm2:
                    title = title[:-1] + "①②③④⑤⑥⑦⑧⑨"[int(sm2.group(1)) - 1] + "：" + sm2.group(2)
                    i += 1
            title = re.sub(r"\s+(?:新教務系統|校務行政資訊系統)[:：].*$", "", title)
            if title.count("（") > title.count("）"):
                title = title[:title.rfind("（")]
            title = title.strip()
            sy = base_year + 1 if (sem == 1 and smonth < 6) else base_year
            try:
                start = date(sy, smonth, d1)
                end = start
                if end_d:
                    em_ = end_m or smonth
                    end = date(sy + (1 if em_ < smonth else 0), em_, end_d)
            except ValueError:
                continue
            title = re.sub(r"\s*○\s*", "", title).rstrip("：:")
            raw = f"{ln} | {' '.join(times)} | {title}"
            ev = make_event(C.sha1("tt", roc, sem, start, end, title), title, start, end, source_url,
                            note=("時間 " + ("~".join(times) if len(times) == 2 else " ".join(times))) if times else None, default_cat="學校",
                            title_prefix="")
            ev["raw_text"] = raw
            ev["semester"] = f"{roc}-{sem}"  # document's semester (June items are 115-1 preparation)
            out.append(ev)
    return out


def scrape_timetable(sess):
    pdf = sess.get(TIMETABLE_PDF).content
    return parse_timetable_pdf(pdf, TIMETABLE_PDF)


# ---------------------------------------------------------------------------
# 4) news.scu.edu.tw announcements
# ---------------------------------------------------------------------------
UNIT_PREFIX_RE = re.compile(r"^\s*[【\[]([^】\]]{2,20})[】\]]")


def unit_from_title(title):
    m = UNIT_PREFIX_RE.match(title)
    if not m:
        return None
    u = m.group(1).strip()
    u = re.sub(r"(轉知訊息|轉知|公告)$", "", u).strip()
    # only accept things that look like an office/department name, not topics like 【就學貸款】
    if not re.search(r"(中心|組|處|室|系|館|學院|委員會|辦公室|基地|研究所|學程|部|社|會)$", u):
        return None
    return u


def parse_news_list(html, base=NEWS_LIST):
    s = BeautifulSoup(html, "lxml")
    items = []
    for tr in s.select("table tbody tr"):
        tds = tr.find_all("td")
        a = tr.find("a", href=True)
        if len(tds) < 3 or not a:
            continue
        m = re.search(r"/news/(\d+)", a["href"])
        if not m:
            continue
        title = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        d = tds[2].get_text(strip=True).replace("/", "-")
        items.append({
            "source_name": "news", "news_id": m.group(1), "title": title,
            "date": d if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) else None,
            "category": tds[0].get_text(strip=True) or None,
            "unit": None if tds[0].get_text(strip=True) == "媒體報導" else unit_from_title(title),
            "tag": C.categorize(title, "公告"),
            "url": urljoin(base, a["href"]),
        })
    last_page = max([int(x) for x in re.findall(r"news\?page=(\d+)", html)] or [1])
    return items, last_page


def news_detail_unit(sess, url):
    t = BeautifulSoup(sess.get(url).text, "lxml").get_text("\n", strip=True)
    m = re.search(r"資料提供\s*[:：]\s*([^\n]{2,30})", t)
    return m.group(1).strip() if m else None


def scrape_news(sess, con, pages, detail_limit, full=False):
    all_items = []
    for p in range(1, pages + 1):
        url = NEWS_LIST if p == 1 else f"{NEWS_LIST}?page={p}"
        items, last_page = parse_news_list(sess.get(url).text)
        all_items += items
        known = sum(1 for it in items if con.execute(
            "SELECT 1 FROM announcements WHERE source_name='news' AND news_id=?", (it["news_id"],)).fetchone())
        if not full and items and known == len(items):
            log(f"  news: page {p} fully known -> stop paging")
            break
        if p >= last_page:
            break
    # optional: fetch detail pages of NEW items without a unit prefix
    n = 0
    for it in all_items:
        if n >= detail_limit:
            break
        exists = con.execute("SELECT unit FROM announcements WHERE source_name='news' AND news_id=?",
                             (it["news_id"],)).fetchone()
        if it["category"] == "媒體報導":
            continue
        if it["unit"] is None and (exists is None or exists["unit"] is None):
            it["unit"] = news_detail_unit(sess, it["url"])
            n += 1
    return all_items


def scrape_unit_lists(sess):
    out = []
    for source_name, unit, url in UNIT_LISTS:
        s = BeautifulSoup(sess.get(url).text, "lxml")
        for tr in s.select("table tr"):
            tds = tr.find_all("td")
            if len(tds) != 2:
                continue
            title = re.sub(r"\s+", " ", tds[0].get_text(" ", strip=True))
            d = tds[1].get_text(strip=True)
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
                continue
            out.append({"source_name": source_name, "news_id": C.sha1(title, d)[:16], "title": title, "date": d,
                        "unit": unit, "category": unit, "tag": C.categorize(title, "公告"),
                        "url": url})
    return out


# ---------------------------------------------------------------------------
# 5) dated deadlines mentioned in announcement titles  (e.g. "(申請日期115/09/17~115/09/30截止)")
# ---------------------------------------------------------------------------
TITLE_RANGE_RES = [
    re.compile(r"(?P<y1>1\d{2})[/.](?P<m1>\d{1,2})[/.](?P<d1>\d{1,2})\s*[~～\-至]\s*(?:(?P<y2>1\d{2})[/.])?(?P<m2>\d{1,2})[/.](?P<d2>\d{1,2})"),
    re.compile(r"(?P<y1>1\d{2})年(?P<m1>\d{1,2})月(?P<d1>\d{1,2})日(?:\s*[（(][一二三四五六日][)）])?\s*(?:起)?\s*(?:至|~|～)\s*"
               r"(?:(?P<y2>1\d{2})年)?(?:(?P<m2>\d{1,2})月)?(?P<d2>\d{1,2})日"),
]
TITLE_DEADLINE_RE = re.compile(r"(?:至|截止|前)[^0-9]{0,4}(?P<y1>1\d{2})年(?P<m1>\d{1,2})月(?P<d1>\d{1,2})日|"
                               r"(?P<y3>1\d{2})年(?P<m3>\d{1,2})月(?P<d3>\d{1,2})日[（(]?[一二三四五六日]?[)）]?\s*(?:止|截止|前)")


def events_from_titles(con, min_date):
    out = []
    rows = con.execute("SELECT * FROM announcements WHERE date >= ?", (min_date,)).fetchall()
    for a in rows:
        t = a["title"]
        start = end = None
        for rx in TITLE_RANGE_RES:
            m = rx.search(t)
            if m:
                try:
                    y1 = C.roc_to_ad(int(m.group("y1")))
                    start = date(y1, int(m.group("m1")), int(m.group("d1")))
                    y2 = C.roc_to_ad(int(m.group("y2"))) if m.group("y2") else y1
                    m2 = int(m.group("m2")) if m.group("m2") else start.month
                    end = date(y2, m2, int(m.group("d2")))
                    if end < start:
                        start = end = None
                except ValueError:
                    start = end = None
                break
        if start is None:
            m = TITLE_DEADLINE_RE.search(t)
            if m:
                g = (m.group("y1"), m.group("m1"), m.group("d1")) if m.group("y1") else (m.group("y3"), m.group("m3"), m.group("d3"))
                try:
                    start = end = date(C.roc_to_ad(int(g[0])), int(g[1]), int(g[2]))
                except ValueError:
                    pass
        if start is None:
            continue
        cat = C.categorize(t, "公告")
        out.append({
            "uid": f"{a['source_name']}:{a['news_id']}", "title": re.sub(r"\s+", " ", t).strip(),
            "category": cat, "start_date": start.isoformat(),
            "end_date": end.isoformat() if end and end != start else None,
            "source_url": a["url"], "raw_text": t, "semester": C.semester_of(start),
            "audience": C.audience_of(t), "note": f"由公告標題擷取（{a['unit'] or ''} {a['date']}）",
        })
    return out


# ---------------------------------------------------------------------------
# cross-check ICS vs PDF
# ---------------------------------------------------------------------------
def crosscheck(con, year):
    lo, hi = C.academic_year_window(year)
    q = ("SELECT title,start_date,end_date,id FROM events WHERE source_name=? AND is_active=1 "
         "AND start_date BETWEEN ? AND ?")
    ics = con.execute(q, ("scu_calendar_ics", lo.isoformat(), hi.isoformat())).fetchall()
    pdf = con.execute(q, ("scu_calendar_pdf", lo.isoformat(), hi.isoformat())).fetchall()
    norm = lambda t: re.sub(r"[\s。，,、()（）]", "", t)
    pdf_by = {}
    for r in pdf:
        pdf_by.setdefault(norm(r["title"]), []).append(r)
    report, matched = [], 0
    for r in ics:
        cands = pdf_by.get(norm(r["title"]), [])
        if not cands:
            report.append(f"ICS only: {r['start_date']} {r['title']}")
            continue
        best = min(cands, key=lambda c: abs((date.fromisoformat(c["start_date"]) - date.fromisoformat(r["start_date"])).days))
        bs, be = best["start_date"], best["end_date"] or best["start_date"]
        rs, re_ = r["start_date"], r["end_date"] or r["start_date"]
        if (bs, be) == (rs, re_) or ("補假" in r["title"] and rs <= bs and be <= re_):
            # identical, or the ICS range just also covers the 補假 day mentioned in the title
            matched += 1
            if bs != rs or be != re_:
                report.append(f"OK (ICS 含補假日): {r['title']}: ICS {rs}~{re_} / PDF {bs}~{be}")
            old = con.execute("SELECT note FROM events WHERE id=?", (r["id"],)).fetchone()[0]
            if old and "與行事曆PDF不一致" in old:
                new_note = "；".join(p for p in old.split("；") if "與行事曆PDF不一致" not in p) or None
                con.execute("UPDATE events SET note=? WHERE id=?", (new_note, r["id"]))
        else:
            msg = f"PDF 寫 {best['start_date']}~{best['end_date'] or best['start_date']}"
            report.append(f"DATE MISMATCH: {r['title']}: ICS {r['start_date']}~{r['end_date'] or r['start_date']} vs {msg}")
            con.execute("UPDATE events SET note = TRIM(COALESCE(note || '；','') || ?) WHERE id=? AND "
                        "(note IS NULL OR note NOT LIKE ?)", (f"與行事曆PDF不一致：{msg}", r["id"], f"%{msg}%"))
    ics_titles = {norm(r["title"]) for r in ics}
    for r in pdf:
        if norm(r["title"]) not in ics_titles:
            report.append(f"PDF only: {r['start_date']} {r['title']}")
    con.commit()
    return matched, len(ics), len(pdf), report


# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--year", type=int, default=115, help="ROC academic year for the calendar window")
    ap.add_argument("--only", default="ics,pdf,timetable,news,units,titles")
    ap.add_argument("--news-pages", type=int, default=3)
    ap.add_argument("--news-full", action="store_true", help="don't stop paging at known items")
    ap.add_argument("--news-detail-limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=C.MIN_INTERVAL)
    args = ap.parse_args(argv)
    only = set(args.only.split(","))

    con = db_connect(args.db)
    sess = C.PoliteSession(min_interval=args.delay, log=log)
    fetched = C.now_iso()
    rc = 0

    def run(name, fn):
        nonlocal rc
        started = C.now_iso()
        log(f"[{name}]")
        try:
            n, msg = fn()
            log(f"  -> {msg}")
            log_crawl(con, name, started, "ok", n, msg)
        except C.Blocked as e:
            log_crawl(con, name, started, "blocked", 0, str(e))
            raise
        except Exception as e:  # keep going with other sources
            rc = 1
            log(f"  !! {name} failed: {e!r}")
            log_crawl(con, name, started, "error", 0, repr(e))

    try:
        if "ics" in only:
            def f():
                evs, win = scrape_ics(sess, args.year)
                r = upsert_events(con, "scu_calendar_ics", evs, fetched, win)
                return len(evs), f"{len(evs)} events (ins/upd/same/deact = {r})"
            run("scu_calendar_ics", f)
        if "pdf" in only:
            def f():
                evs = scrape_calendar_pdf(sess, args.year)
                r = upsert_events(con, "scu_calendar_pdf", evs, fetched, C.academic_year_window(args.year))
                return len(evs), f"{len(evs)} events (ins/upd/same/deact = {r})"
            run("scu_calendar_pdf", f)
        if "timetable" in only:
            def f():
                evs = scrape_timetable(sess)
                # sanity check: timetable '上課開始' must equal the calendar's 開學日
                ks = [e for e in evs if e["title"].startswith("上課開始")]
                cal = con.execute("SELECT start_date FROM events WHERE source_name='scu_calendar_ics' AND is_active=1 "
                                  "AND title LIKE '開學日%'").fetchall()
                if ks and cal and ks[0]["start_date"] not in {c[0] for c in cal}:
                    raise RuntimeError(f"timetable month detection suspect: 上課開始={ks[0]['start_date']} "
                                       f"vs calendar {[c[0] for c in cal]}; not stored")
                r = upsert_events(con, "scu_course_timetable", evs, fetched)
                return len(evs), f"{len(evs)} events (ins/upd/same/deact = {r})"
            run("scu_course_timetable", f)
        if "news" in only:
            def f():
                items = scrape_news(sess, con, args.news_pages, args.news_detail_limit, args.news_full)
                new = upsert_announcements(con, items, fetched)
                return len(items), f"{len(items)} announcements seen, {new} new"
            run("news", f)
        if "units" in only:
            def f():
                items = scrape_unit_lists(sess)
                new = upsert_announcements(con, items, fetched)
                return len(items), f"{len(items)} unit announcements seen, {new} new"
            run("units", f)
        if "titles" in only:
            def f():
                lo, _ = C.academic_year_window(args.year)
                evs = events_from_titles(con, (lo - timedelta(days=62)).isoformat())
                r = upsert_events(con, "announcement_title", evs, fetched)
                return len(evs), f"{len(evs)} dated items from announcement titles (ins/upd/same = {r[:3]})"
            run("announcement_title", f)
        if {"ics", "pdf"} <= only:
            matched, n_ics, n_pdf, report = crosscheck(con, args.year)
            log(f"[crosscheck] ICS {n_ics} vs PDF {n_pdf}: {matched} identical")
            with open(os.path.join(HERE, "out", "crosscheck.txt"), "w", encoding="utf-8") as fh:
                fh.write(f"# {C.now_iso()} ICS {n_ics} / PDF {n_pdf} / identical {matched}\n" + "\n".join(report) + "\n")
            for line in report:
                log("  " + line)
    except C.Blocked as e:
        log(f"STOPPED: {e}")
        return 2
    finally:
        log(f"done: {sess.n_requests} HTTP requests")
    return rc


if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    sys.exit(main())
