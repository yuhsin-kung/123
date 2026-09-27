#!/usr/bin/env python3
"""
Soochow University (東吳大學) public class timetable scraper — prototype.

Source: https://web.sys.scu.edu.tw/class40.asp?option=1  (frameset)
  -> query form lives in  class401.asp   (UTF-8, dropdown data in inline JS arrays)
  -> results come from    class42.asp    (POST, UTF-8)

Update model: ONE full crawl per semester (e.g. 115-1). A crawl for a semester is
collected fully in memory first, then swapped into SQLite in a single transaction
(old rows for that semester are deleted), and a row in scrape_runs records it.
Raw HTML for every request is archived under raw/<semester>/<run_ts>/.

Usage:
  python scrape_class40.py options [--program 學士班] [--dept 資料科學系]
  python scrape_class40.py fetch --semester 115-1 --class-value 717332資科三Ｂ　
  python scrape_class40.py fetch --semester 115-1 --profile "大三 資科 B班"
  python scrape_class40.py crawl --semester 115-1 --all [--limit 3] [--program 學士班 --dept 資料科學系]
  python scrape_class40.py map "大三 資科 B班"
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
from pathlib import Path
from typing import Iterable, Optional

import requests
from bs4 import BeautifulSoup

BASE = "https://web.sys.scu.edu.tw/"
FORM_URL = BASE + "class401.asp"        # the frame that holds the form
FRAMESET_URL = BASE + "class40.asp?option=1"
RESULT_URL = BASE + "class42.asp"       # form action (method=POST, target=bottom)
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) scu-timetable-research/0.1 "
              "(personal timetable tool; 1 req/s)")
MIN_INTERVAL = 1.2                      # seconds between requests (polite: <1 req/s)

RULE_URL = BASE + "SelectCar/selrule12.asp"   # public 選課限制資料查詢 (Big5), GET ?syear=&smester=&courid=&corder=

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "scu_timetable.db"
RAW_DIR = HERE / "raw"

# 節次 -> (start, end), from /fileMSG/Course/classtable_hlp.html
PERIOD_TIMES = {
    "1": ("08:10", "09:00"), "2": ("09:10", "10:00"), "3": ("10:10", "11:00"),
    "4": ("11:10", "12:00"), "E": ("12:10", "13:00"), "5": ("13:10", "14:00"),
    "6": ("14:10", "15:00"), "7": ("15:10", "16:00"), "8": ("16:10", "17:00"),
    "9": ("17:10", "18:20"),  # help page: "789" => 17:10-18:00, "9AB" => 17:30-18:20
    "A": ("18:25", "19:15"), "B": ("19:20", "20:10"), "C": ("20:20", "21:10"),
    "D": ("21:15", "22:05"),
    # F slots are special (體育/研究生): F1 13:00-15:10, F2 12:00-14:00, F3 16:00-17:50, F4 12:00-14:00
}
PERIOD_ORDER = "1234E56789ABCD"
WEEKDAYS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}
CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7}
NUM_CN = {v: k for k, v in CN_NUM.items()}
PROGRAM_ALIASES = {  # free text -> program code (first char of clsid1 value)
    "學士班": "1", "大學部": "1", "大": "1", "日間部": "1",
    "碩士班": "3", "碩": "3", "研究所": "3",
    "博士班": "4", "博": "4",
    "學後專": "5", "學後第二專長": "5",
    "進修學士班": "6", "進修部": "6", "夜間部": "6",
    "碩士在職專班": "7", "在職專班": "7", "碩專": "7",
}


def nfkc(s: str) -> str:
    """Normalize full-width chars (Ａ->A, ＧＡ->GA, '　'->' ') and strip."""
    return unicodedata.normalize("NFKC", s or "").replace("\xa0", " ").strip()


# --------------------------------------------------------------------------- HTTP
class PoliteClient:
    def __init__(self, archive_dir: Optional[Path] = None, min_interval: float = MIN_INTERVAL):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": USER_AGENT,
                               "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.5"})
        self.min_interval = min_interval
        self._last = 0.0
        self.archive_dir = archive_dir
        self.n_requests = 0

    def _wait(self):
        delta = time.monotonic() - self._last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last = time.monotonic()

    def request(self, method: str, url: str, archive_name: Optional[str] = None, **kw) -> str:
        for attempt in range(3):
            self._wait()
            self.n_requests += 1
            r = self.s.request(method, url, timeout=30, **kw)
            if r.status_code in (403, 429):
                raise RuntimeError(f"Blocked/rate-limited ({r.status_code}) on {url}; stopping.")
            if r.status_code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            html = decode_html(r.content)
            if self.archive_dir and archive_name:
                self.archive_dir.mkdir(parents=True, exist_ok=True)
                (self.archive_dir / archive_name).write_bytes(r.content)
            return html
        raise RuntimeError(f"Server errors on {url}")

    def get_form_page(self) -> str:
        # Touch the frameset first (sets ASPSESSIONID / BIGipServer cookies like a browser would).
        self.request("GET", FRAMESET_URL)
        return self.request("GET", FORM_URL, archive_name="class401.asp.html",
                            headers={"Referer": FRAMESET_URL})

    def post_timetable(self, codes: dict, archive_name: Optional[str] = None) -> str:
        data = {k: str(v).encode("utf-8") for k, v in codes.items()}  # form page is UTF-8
        return self.request("POST", RESULT_URL, archive_name=archive_name, data=data,
                            headers={"Referer": FORM_URL})


def decode_html(b: bytes) -> str:
    """Pages mix encodings: class401/class42 are UTF-8, older static pages are Big5/cp950."""
    head = b[:1024].decode("ascii", "ignore").lower()
    if "charset=utf-8" in head:
        return b.decode("utf-8", "replace")
    if "charset=big5" in head:
        return b.decode("cp950", "replace")
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp950", "replace")


# --------------------------------------------------------------------------- options
@dataclasses.dataclass
class Program:
    code: str          # '1'
    value: str         # '1學士班' (form value of clsid1)
    label: str         # '學士班'
    index: int         # position in dropdown == index into JS key[]/key1[]


@dataclasses.dataclass
class Department:
    program_code: str
    value: str         # '7373資料科學系' (form value of clsid02)
    label: str         # '資料科學系'
    class_key: str     # program_code + value[2:4] -> '173' (index into JS class1[]/class1v[])


@dataclasses.dataclass
class SchoolClass:
    program_code: str
    dept_value: str
    value: str         # '717332資科三Ｂ　' (form value of clsid34, trailing U+3000 kept!)
    label: str         # '資科三Ｂ'
    grade: Optional[int]
    section: Optional[str]  # 'A','B',... or None
    abbr: str          # '資科'


@dataclasses.dataclass
class FormOptions:
    programs: list
    departments: list
    classes: list
    default_year: Optional[str]
    default_semester: Optional[str]


_JS_ASSIGN = re.compile(r'(key1?|class1v?)\[(\d+)\]\[(\d+)\]\s*=\s*"([^"]*)"')


def parse_class_label(label: str):
    """'資科三Ｂ　' -> ('資科', 3, 'B'); '資科專四' -> ('資科專', 4, None); '人社院' -> ('人社院', None, None)."""
    t = nfkc(label)
    m = re.match(r"^(.*?)([一二三四五六七])([A-Z])?$", t)
    if not m:
        return t, None, None
    return m.group(1), CN_NUM[m.group(2)], m.group(3)


def parse_options(html: str) -> FormOptions:
    soup = BeautifulSoup(html, "lxml")
    sel = soup.find("select", attrs={"name": "clsid1"})
    programs = [Program(code=o["value"][0], value=o["value"], label=o.get_text(strip=True), index=i)
                for i, o in enumerate(sel.find_all("option"))]
    arrays: dict = {"key": {}, "key1": {}, "class1": {}, "class1v": {}}
    for name, i, j, val in _JS_ASSIGN.findall(html):
        arrays[name].setdefault(int(i), {})[int(j)] = val
    departments, classes = [], []
    for p in programs:
        labels, values = arrays["key"].get(p.index, {}), arrays["key1"].get(p.index, {})
        for j in sorted(values):
            v = values[j]
            # mirror JS Buildclsid34(): cls2 = clsid1[0] + clsid02.substr(2,2); class1[cls2] (numeric index)
            ck = str(int(p.code + v[2:4])) if (p.code + v[2:4]).isdigit() else p.code + v[2:4]
            d = Department(p.code, v, labels.get(j, v[4:]), ck)
            departments.append(d)
            cl, cv = arrays["class1"].get(int(ck), {}), arrays["class1v"].get(int(ck), {})
            for k in sorted(cv):
                lab = cl.get(k, cv[k][6:])
                abbr, grade, section = parse_class_label(lab)
                classes.append(SchoolClass(p.code, v, cv[k], nfkc(lab), grade, section, abbr))
    yr = soup.find("input", attrs={"name": "syear"})
    sm = soup.find("select", attrs={"name": "smester"})
    sm_sel = sm.find("option", selected=True) if sm else None
    return FormOptions(programs, departments, classes,
                       yr.get("value") if yr else None,
                       sm_sel.get("value") if sm_sel else None)


# --------------------------------------------------------------------------- timetable
COLS = ["offering_class", "selection_no", "course_code", "course_name", "group_name",
        "term_type", "req_elective", "credits", "hours", "capacity", "teacher",
        "weekday", "periods", "week_type", "room", "note"]


def _cell(td) -> str:
    return nfkc(td.get_text(" ", strip=True))


def periods_to_time(periods: str):
    ps = [p for p in periods if p in PERIOD_TIMES]
    if not ps:
        return None, None
    ps.sort(key=PERIOD_ORDER.index)
    start, end = PERIOD_TIMES[ps[0]][0], PERIOD_TIMES[ps[-1]][1]
    if ps[-1] == "9" and len(ps) > 1 and ps[-2] in "78":
        end = "18:00"                       # '789' form
    if ps[0] == "9" and len(ps) > 1:
        start = "17:30"                     # '9AB' form
    return start, end


def parse_timetable(html: str) -> dict:
    """Return {'caption':..., 'courses':[{..., 'sessions':[...]}, ...]}.
    Rows with an empty course column are extra meeting times of the previous course."""
    soup = BeautifulSoup(html, "lxml")
    cap = soup.find("caption")
    caption = nfkc(cap.get_text(" ", strip=True)) if cap else ""
    courses: list = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 16:
            continue
        row = dict(zip(COLS, (_cell(td) for td in tds[:16])))
        a_plan = tds[3].find("a")
        a_teacher = tds[10].find("a")
        sess = {"teacher": row["teacher"], "weekday_label": row["weekday"],
                "weekday": WEEKDAYS.get(row["weekday"]), "periods": row["periods"],
                "week_type": row["week_type"], "room": row["room"]}
        sess["start_time"], sess["end_time"] = periods_to_time(row["periods"])
        if not row["course_code"] and courses:          # continuation row
            courses[-1]["sessions"].append(sess)
            continue
        c = {k: row[k] for k in ("offering_class", "selection_no", "course_code", "course_name",
                                 "group_name", "term_type", "req_elective", "teacher", "note")}
        c["credits"] = _num(row["credits"])
        c["hours"] = _num(row["hours"])
        c["capacity"] = int(row["capacity"]) if row["capacity"].isdigit() else None
        c["plan_url"] = BASE.rstrip("/") + a_plan["href"] if a_plan and a_plan.get("href") else None
        c["teacher_url"] = BASE.rstrip("/") + a_teacher["href"] if a_teacher and a_teacher.get("href") else None
        c["sessions"] = [sess] if (sess["weekday"] or sess["periods"] or sess["room"]) else []
        courses.append(c)
    return {"caption": caption, "courses": courses}


def _num(s: str):
    try:
        f = float(s)
        return int(f) if f.is_integer() else f
    except ValueError:
        return None


# --------------------------------------------------------------------------- profile mapping
def parse_semester(sem: str):
    m = re.fullmatch(r"(\d{2,3})-([12])", sem.strip())
    if not m:
        raise ValueError(f"semester must look like 115-1, got {sem!r}")
    return m.group(1), m.group(2)


def parse_profile(profile) -> dict:
    """'大三 資科 B班' / '碩一 資科' / dict -> {'program_code','dept','grade','section'}"""
    if isinstance(profile, dict):
        p = dict(profile)
        prog = p.get("program", "學士班")
        grade = p.get("grade")
        if isinstance(grade, str):
            grade = CN_NUM.get(grade) or int(grade)
        sec = p.get("class") or p.get("section")
        sec = nfkc(sec).upper().replace("班", "") if sec else None
        return {"program_code": PROGRAM_ALIASES.get(prog, prog if prog.isdigit() else "1"),
                "dept": p.get("dept"), "grade": grade, "section": sec}
    t = nfkc(profile)
    prog_code, grade = "1", None
    m = re.search(r"(大|碩專|碩|博|進修)([一二三四五六七1-7])", t)
    if m:
        prog_code = {"大": "1", "碩": "3", "博": "4", "進修": "6", "碩專": "7"}[m.group(1)]
        g = m.group(2)
        grade = CN_NUM.get(g) or int(g)
        t = t.replace(m.group(0), " ")
    for alias, code in sorted(PROGRAM_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if len(alias) > 1 and alias in t:
            prog_code = code
            t = t.replace(alias, " ")
            break
    sec = None
    m = re.search(r"([A-Za-z])\s*班?", t)
    if m:
        sec = m.group(1).upper()
        t = t.replace(m.group(0), " ")
    dept = " ".join(t.split()) or None
    if dept and grade is None:              # compact class label form: '資科三B' / '資科三'
        m = re.fullmatch(r"(.+?)([一二三四五六七])", dept)
        if m:
            dept, grade = m.group(1), CN_NUM[m.group(2)]
    return {"program_code": prog_code, "dept": dept, "grade": grade, "section": sec}


def profile_to_codes(profile, options: FormOptions, semester: Optional[str] = None) -> dict:
    """Map a student profile to the POST fields of class42.asp.
    dept may be the full label ('資料科學系') or the class-label abbreviation ('資科')."""
    pp = parse_profile(profile)
    dept_q = nfkc(pp["dept"] or "")
    cands = [c for c in options.classes if c.program_code == pp["program_code"]]
    dept_by_value = {(d.program_code, d.value): d for d in options.departments}

    def dept_matches(c):
        d = dept_by_value[(c.program_code, c.dept_value)]
        return dept_q and (dept_q == d.label or dept_q == c.abbr or dept_q in d.label
                           or d.label.startswith(dept_q) or _abbr_match(dept_q, d.label))

    cands = [c for c in cands if dept_matches(c)]
    if pp["grade"] is not None:
        cands = [c for c in cands if c.grade == pp["grade"]]
    if pp["section"]:
        cands = [c for c in cands if c.section == pp["section"]]
    # dedupe by class value (a class can be listed under a college entry and its dept)
    uniq = {c.value: c for c in cands}
    if not uniq:
        raise LookupError(f"No class matches profile {profile!r} -> {pp}")
    if len(uniq) > 1:
        raise LookupError(f"Ambiguous profile {profile!r}: {[c.label for c in uniq.values()]}")
    c = next(iter(uniq.values()))
    prog = next(p for p in options.programs if p.code == c.program_code)
    year, sm = parse_semester(semester) if semester else (options.default_year, options.default_semester)
    return {"clsid1": prog.value, "clsid02": c.dept_value, "clsid34": c.value,
            "syear": year, "smester": sm}


def _abbr_match(q: str, label: str) -> bool:
    """'資科' ~ '資料科學系': every char of q appears in order in label."""
    it = iter(label)
    return len(q) >= 2 and all(ch in it for ch in q)


# --------------------------------------------------------------------------- SQLite
SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS scrape_runs (
  id INTEGER PRIMARY KEY, semester TEXT NOT NULL, started_at TEXT NOT NULL,
  finished_at TEXT, status TEXT NOT NULL, n_classes INTEGER, n_requests INTEGER,
  raw_dir TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS programs (
  id INTEGER PRIMARY KEY, semester TEXT NOT NULL, code TEXT NOT NULL,
  form_value TEXT NOT NULL, label TEXT NOT NULL, scrape_run_id INTEGER REFERENCES scrape_runs(id),
  scraped_at TEXT NOT NULL, UNIQUE(semester, code));
CREATE TABLE IF NOT EXISTS departments (
  id INTEGER PRIMARY KEY, semester TEXT NOT NULL,
  program_id INTEGER NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
  form_value TEXT NOT NULL, label TEXT NOT NULL, class_key TEXT NOT NULL,
  scraped_at TEXT NOT NULL, UNIQUE(semester, program_id, form_value));
CREATE TABLE IF NOT EXISTS classes (
  id INTEGER PRIMARY KEY, semester TEXT NOT NULL,
  department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
  form_value TEXT NOT NULL, label TEXT NOT NULL, abbr TEXT, grade INTEGER, section TEXT,
  timetable_scraped_at TEXT, scraped_at TEXT NOT NULL,
  UNIQUE(semester, department_id, form_value));
CREATE TABLE IF NOT EXISTS courses (
  id INTEGER PRIMARY KEY, semester TEXT NOT NULL,
  course_code TEXT NOT NULL,          -- 科目代碼 e.g. BDD30102
  selection_no TEXT NOT NULL DEFAULT '',  -- 選課編號 e.g. 4264 ('' for placeholders like 通識/系會)
  name TEXT NOT NULL, offering_class TEXT, group_name TEXT, term_type TEXT,  -- 全/單
  credits REAL, hours REAL, capacity INTEGER, teacher TEXT, note TEXT,
  plan_url TEXT, teacher_url TEXT, scraped_at TEXT NOT NULL,
  -- identity: 選課編號 when present (cross-listed courses appear on many class timetables and
  -- the 開課班級 column just echoes the queried class); else course_code@class for placeholders
  offering_key TEXT NOT NULL,
  UNIQUE(semester, course_code, offering_key));
CREATE TABLE IF NOT EXISTS class_courses (   -- which courses appear on which class timetable
  class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
  course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  req_elective TEXT,                  -- 必/選 (can differ per class)
  PRIMARY KEY (class_id, course_id));
CREATE TABLE IF NOT EXISTS course_sessions (
  id INTEGER PRIMARY KEY,
  course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  weekday INTEGER, periods TEXT, start_time TEXT, end_time TEXT,
  week_type TEXT, room TEXT, teacher TEXT,
  UNIQUE(course_id, weekday, periods, room, week_type));
CREATE TABLE IF NOT EXISTS course_rules (       -- raw rows of selrule12.asp (選課限制資料查詢)
  id INTEGER PRIMARY KEY, semester TEXT NOT NULL, course_code TEXT NOT NULL,
  rule_code TEXT, description TEXT, phase TEXT,      -- phase: 開學前 / 開學後 / ''
  allow INTEGER,                                     -- 1 可選 / 0 不可選 / NULL
  dimension TEXT, rule_values TEXT,                  -- '年級', '["二","三"]' (JSON)
  exceptions TEXT, raw TEXT, scraped_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_rules ON course_rules(semester, course_code);
CREATE TABLE IF NOT EXISTS course_restrictions (  -- normalized, one row per (semester, course_code)
  semester TEXT NOT NULL, course_code TEXT NOT NULL,
  min_grade INTEGER, max_grade INTEGER, grades TEXT,  -- grades: JSON list of allowed grades
  dept_only TEXT, program_only TEXT, class_only TEXT, -- JSON lists (NULL = no restriction)
  dept_exclude TEXT,                                  -- JSON list: 不可選 學系 (e.g. ["英文系"])
  exceptions TEXT, other_text TEXT,
  source TEXT NOT NULL,                               -- 'selrule' | 'note' | 'selrule+note' | 'none'
  rules_checked INTEGER NOT NULL DEFAULT 0,           -- 1 if selrule12 page was fetched
  scraped_at TEXT NOT NULL,
  PRIMARY KEY (semester, course_code));
CREATE TABLE IF NOT EXISTS second_expertise_courses (  -- 網路課表「第二專長課表查詢」(SecExpQueryCls.aspx)
  semester TEXT NOT NULL, course_code TEXT NOT NULL, selection_no TEXT NOT NULL DEFAULT '',
  name TEXT, track TEXT,                               -- track = 開課班級 column = 第二專長名稱 (e.g. 故宮文創)
  group_name TEXT, req_elective TEXT, credits REAL, capacity INTEGER, teacher TEXT,
  weekday TEXT, periods TEXT, room TEXT, week_type TEXT, scraped_at TEXT NOT NULL,
  UNIQUE(semester, course_code, selection_no, track, weekday, periods));
CREATE INDEX IF NOT EXISTS ix_courses_sem ON courses(semester, course_code);
CREATE INDEX IF NOT EXISTS ix_classes_sem ON classes(semester, label);
"""


def db_connect(path=DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(course_restrictions)")}
    if "dept_exclude" not in cols:  # migrate DBs created before this column existed
        con.execute("ALTER TABLE course_restrictions ADD COLUMN dept_exclude TEXT")
    return con


def replace_semester(con, semester: str, options: FormOptions, timetables: dict,
                     run_meta: dict, full: bool) -> int:
    """Swap data for one semester atomically.
    full=True : delete ALL rows of that semester first (per-semester full crawl).
    full=False: upsert only the classes given (ad-hoc single-class fetch)."""
    now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    with con:  # single transaction
        cur = con.execute(
            "INSERT INTO scrape_runs(semester, started_at, finished_at, status, n_classes, n_requests, raw_dir, note)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (semester, run_meta["started_at"], now, "ok", len(timetables),
             run_meta.get("n_requests"), run_meta.get("raw_dir"), run_meta.get("note")))
        run_id = cur.lastrowid
        if full:
            con.execute("DELETE FROM courses WHERE semester=?", (semester,))
            con.execute("DELETE FROM programs WHERE semester=?", (semester,))
        prog_ids, dept_ids, class_ids = {}, {}, {}
        for p in options.programs:
            con.execute("INSERT INTO programs(semester, code, form_value, label, scrape_run_id, scraped_at)"
                        " VALUES (?,?,?,?,?,?) ON CONFLICT(semester, code) DO UPDATE SET"
                        " label=excluded.label, scrape_run_id=excluded.scrape_run_id, scraped_at=excluded.scraped_at",
                        (semester, p.code, p.value, p.label, run_id, now))
            prog_ids[p.code] = con.execute("SELECT id FROM programs WHERE semester=? AND code=?",
                                           (semester, p.code)).fetchone()[0]
        for d in options.departments:
            con.execute("INSERT INTO departments(semester, program_id, form_value, label, class_key, scraped_at)"
                        " VALUES (?,?,?,?,?,?) ON CONFLICT DO UPDATE SET label=excluded.label, scraped_at=excluded.scraped_at",
                        (semester, prog_ids[d.program_code], d.value, d.label, d.class_key, now))
            dept_ids[(d.program_code, d.value)] = con.execute(
                "SELECT id FROM departments WHERE semester=? AND program_id=? AND form_value=?",
                (semester, prog_ids[d.program_code], d.value)).fetchone()[0]
        for c in options.classes:
            did = dept_ids[(c.program_code, c.dept_value)]
            con.execute("INSERT INTO classes(semester, department_id, form_value, label, abbr, grade, section, scraped_at)"
                        " VALUES (?,?,?,?,?,?,?,?) ON CONFLICT DO UPDATE SET label=excluded.label, scraped_at=excluded.scraped_at",
                        (semester, did, c.value, c.label, c.abbr, c.grade, c.section, now))
            class_ids.setdefault(c.value, []).append(con.execute(
                "SELECT id FROM classes WHERE semester=? AND department_id=? AND form_value=?",
                (semester, did, c.value)).fetchone()[0])
        for class_value, tt in timetables.items():
            for cid in class_ids.get(class_value, []):
                con.execute("DELETE FROM class_courses WHERE class_id=?", (cid,))
                con.execute("UPDATE classes SET timetable_scraped_at=? WHERE id=?", (now, cid))
                for c in tt["courses"]:
                    okey = c["selection_no"] or f'{c["course_code"]}@{c["offering_class"]}'
                    con.execute(
                        "INSERT INTO courses(semester, course_code, selection_no, name, offering_class, group_name,"
                        " term_type, credits, hours, capacity, teacher, note, plan_url, teacher_url, scraped_at,"
                        " offering_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                        " ON CONFLICT(semester, course_code, offering_key) DO UPDATE SET"
                        " name=excluded.name, capacity=excluded.capacity, teacher=excluded.teacher,"
                        " note=excluded.note, scraped_at=excluded.scraped_at",
                        (semester, c["course_code"], c["selection_no"], c["course_name"], c["offering_class"],
                         c["group_name"], c["term_type"], c["credits"], c["hours"], c["capacity"],
                         c["teacher"], c["note"], c["plan_url"], c["teacher_url"], now, okey))
                    course_id = con.execute(
                        "SELECT id FROM courses WHERE semester=? AND course_code=? AND offering_key=?",
                        (semester, c["course_code"], okey)).fetchone()[0]
                    con.execute("INSERT OR REPLACE INTO class_courses(class_id, course_id, req_elective) VALUES (?,?,?)",
                                (cid, course_id, c["req_elective"]))
                    for s in c["sessions"]:
                        con.execute(
                            "INSERT OR IGNORE INTO course_sessions(course_id, weekday, periods, start_time, end_time,"
                            " week_type, room, teacher) VALUES (?,?,?,?,?,?,?,?)",
                            (course_id, s["weekday"], s["periods"], s["start_time"], s["end_time"],
                             s["week_type"], s["room"], s["teacher"]))
    return run_id


# --------------------------------------------------------------------------- restrictions
CN_GRADE = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "延": 5}


def parse_rule_page(html: str) -> list:
    """selrule12.asp -> [{rule_code, description, phase, allow, dimension, values, exceptions, raw}]"""
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for tr in soup.find_all("tr"):
        tds = [nfkc(td.get_text(" ", strip=True)) for td in tr.find_all("td", recursive=False)]
        if len(tds) < 4:
            continue
        code, desc, c1, c2 = tds[:4]
        exc = tds[4] if len(tds) > 4 else ""
        desc_clean = re.sub(r"\s+", "", desc)
        phase = "開學前" if "開學前" in desc_clean else "開學後" if "開學後" in desc_clean else ""
        allow = 1 if c1.startswith("可") else 0 if c1.startswith("不") else None
        m = re.match(r"^(.+?)(?:\(人數\))?[:：](.*)$", c2)
        dim, vals = (m.group(1).strip(), [v.strip() for v in re.split(r"[,，、]", m.group(2)) if v.strip()]) if m else ("", [c2] if c2 else [])
        rows.append({"rule_code": code, "description": desc_clean, "phase": phase, "allow": allow,
                     "dimension": dim, "values": vals,
                     "exceptions": [e for e in re.split(r"[,，]", exc) if e], "raw": " | ".join(tds)})
    return rows


def _grade_of(v: str):
    v = v.strip()
    if v.isdigit():
        return int(v)
    return CN_GRADE.get(v[:1]) if v else None


def restriction_from_rules(rows: list, phase: str = "開學後") -> dict:
    """Pick rows of the requested phase (fallback to any) and normalize to
    {min_grade, max_grade, grades, dept_only, program_only, class_only, exceptions, other_text}."""
    # 只取指定階段（預設「開學後」）＋沒有標階段的列。只有「開學前」限制的課，開學後就不限，不能拿開學前的條件套用。
    sel = [r for r in rows if r["phase"] == phase or not r["phase"]]
    out = {"min_grade": None, "max_grade": None, "grades": None, "dept_only": None,
           "program_only": None, "class_only": None, "dept_exclude": None, "exceptions": None, "other_text": None}
    other, exc = [], []
    for r in sel:
        d, vals = r["dimension"], r["values"]
        exc += [e for e in r["exceptions"] if e not in exc]
        if r["allow"] == 1 and d.startswith("年級"):
            gs = sorted({g for g in map(_grade_of, vals) if g})
            if gs:
                out["grades"] = gs; out["min_grade"], out["max_grade"] = gs[0], gs[-1]
        elif r["allow"] == 1 and d.startswith(("學系", "系別", "系所", "學系所")):
            out["dept_only"] = vals
        elif r["allow"] == 1 and d.startswith("部別"):
            out["program_only"] = vals
        elif r["allow"] == 1 and d.startswith("班級"):
            out["class_only"] = vals
        elif r["allow"] == 0 and d.startswith(("學系", "系別", "系所")):
            out["dept_exclude"] = (out["dept_exclude"] or []) + vals
        else:
            other.append(f'{r["description"]}:{r["raw"].split(" | ")[2] if " | " in r["raw"] else ""} {d}:{",".join(vals)}'.strip())
    out["exceptions"] = exc or None
    out["other_text"] = "；".join(other) or None
    return out


NOTE_PATTERNS = [
    (re.compile(r"限([一二三四五1-5])年級以上"), "min_grade"),
    (re.compile(r"限大([一二三四])以上"), "min_grade"),
    (re.compile(r"限([一二三四五1-5])年級(?!以上)"), "grade_eq"),
    (re.compile(r"限大([一二三四])(?!以上)"), "grade_eq"),
    (re.compile(r"限本系"), "own_dept"),
    (re.compile(r"限([\u4e00-\u9fff]{1,10}?(?:學系|系|學程))(?:學生|生)?"), "dept"),
    (re.compile(r"限(學士班|碩士班|博士班|進修學士班|碩士在職專班|碩專班)"), "program"),
    (re.compile(r"擋修|先修"), "prereq"),
]


def restriction_from_note(note: str, group: str = "", offering_dept: str = "") -> dict:
    """Best-effort parse of the free-text 備註 / 組別 columns of class42.asp."""
    t = nfkc(f"{note} {group}")
    out = {"min_grade": None, "max_grade": None, "grades": None, "dept_only": None,
           "program_only": None, "class_only": None, "exceptions": None, "other_text": None}
    hits = []
    for rx, kind in NOTE_PATTERNS:
        for m in rx.finditer(t):
            hits.append(m.group(0))
            if kind == "min_grade":
                out["min_grade"] = _grade_of(m.group(1))
            elif kind == "grade_eq":
                g = _grade_of(m.group(1)); out["grades"] = [g]; out["min_grade"] = out["max_grade"] = g
            elif kind == "own_dept" and offering_dept:
                out["dept_only"] = [offering_dept]
            elif kind == "dept" and m.group(1) != "本系":
                out["dept_only"] = (out["dept_only"] or []) + [m.group(1)]
            elif kind == "program":
                out["program_only"] = [m.group(1)]
    g = nfkc(group)
    if re.fullmatch(r"[\u4e00-\u9fff]{1,4}系", g):          # 組別 '中文系'／'政治系'：該系專屬班（國文、外文常見）
        out["dept_only"] = out["dept_only"] or [g]; hits.append(f"組別:{g}")
    if re.search(r"重.?補修", g):                              # 組別 '重、補修生'／'重補修班'
        hits.append("限重補修生"); out["other_text"] = "限重補修生"
    if hits and not out["other_text"] and not any(out[k] for k in ("min_grade", "grades", "dept_only", "program_only")):
        out["other_text"] = "、".join(hits)
    return out


def classify_note(note: str) -> str:
    t = nfkc(note)
    if not t: return "(空白)"
    if re.search(r"限.{0,4}年級|限大[一二三四]|限[一二三四]年", t): return "年級限制"
    for key, lab in [("年級", "年級限制"), ("限本系", "限本系"), ("學程", "學程相關"), ("擋修", "擋修/先修"),
                     ("先修", "擋修/先修"), ("停開", "停開"), ("遠距", "授課方式:遠距"), ("英語授課", "授課語言"),
                     ("外語授課", "授課語言"), ("限", "其他限修")]:
        if key in t: return lab
    return "其他"


def rule_url(semester: str, course_code: str) -> str:
    y, sm = parse_semester(semester)
    return f"{RULE_URL}?syear={y}&smester={sm}&courid={course_code[:-2]}&corder={course_code[-2:]}"


def store_rules(con, semester: str, results: dict, notes: dict):
    """results: {course_code: rows|None(not fetched)}; notes: {course_code: (note, group, dept)}"""
    now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    with con:
        for code in set(results) | set(notes):
            rows = results.get(code)
            if rows is not None:
                con.execute("DELETE FROM course_rules WHERE semester=? AND course_code=?", (semester, code))
                for r in rows:
                    con.execute("INSERT INTO course_rules(semester, course_code, rule_code, description, phase, allow,"
                                " dimension, rule_values, exceptions, raw, scraped_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                (semester, code, r["rule_code"], r["description"], r["phase"], r["allow"], r["dimension"],
                                 json.dumps(r["values"], ensure_ascii=False), json.dumps(r["exceptions"], ensure_ascii=False),
                                 r["raw"], now))
            else:
                prev = con.execute("SELECT rules_checked FROM course_restrictions WHERE semester=? AND course_code=?",
                                   (semester, code)).fetchone()
                if prev and prev[0]:
                    continue  # keep existing selrule-based restriction
            rr = restriction_from_rules(rows) if rows else None
            nn = restriction_from_note(*notes[code]) if code in notes else None
            merged, src = {}, []
            for part, name in ((rr, "selrule"), (nn, "note")):
                if part and any(v for v in part.values()):
                    src.append(name)
                    for k, v in part.items():
                        if v and not merged.get(k):
                            merged[k] = v
            con.execute("INSERT OR REPLACE INTO course_restrictions(semester, course_code, min_grade, max_grade, grades,"
                        " dept_only, program_only, class_only, exceptions, other_text, source, rules_checked, scraped_at,"
                        " dept_exclude) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (semester, code, merged.get("min_grade"), merged.get("max_grade"),
                         *(json.dumps(merged[k], ensure_ascii=False) if merged.get(k) else None
                           for k in ("grades", "dept_only", "program_only", "class_only", "exceptions")),
                         merged.get("other_text"), "+".join(src) or "none", 1 if rows is not None else 0, now,
                         json.dumps(merged["dept_exclude"], ensure_ascii=False) if merged.get("dept_exclude") else None))


def crawl_rules(semester: str, codes: list, archive_dir: Path, limit: int = 0) -> dict:
    client = PoliteClient(archive_dir=archive_dir)
    out = {}
    codes = codes[:limit or None]
    print(f"fetching {len(codes)} rule pages (~{len(codes) * MIN_INTERVAL / 60:.1f}+ min)")
    for i, code in enumerate(codes, 1):
        html = client.request("GET", rule_url(semester, code), archive_name=f"selrule12_{code}.html",
                              headers={"Referer": BASE + "SelectCar/selrule02.asp"})
        out[code] = parse_rule_page(html)
        if i % 25 == 0 or i == len(codes):
            print(f"  [{i}/{len(codes)}] {code}: {len(out[code])} rule rows")
    return out



# --------------------------------------------------------------------------- 第二專長 (second expertise) course list
# Public ASP.NET page of the new 網路課表 system: 依類別查詢課表 → 第二專長課表查詢. Lists every course that belongs
# to a 第二專長 (課程名稱, 選課編號, 組別, 修選別, 上限, and 開課班級 = the 第二專長 name such as 故宮文創).
# The 學士班選課註冊時間表 says 第二專長 courses are NOT part of 初選 and in the 第二專長 stage
# 「限有登記修讀該專長學生可選該專長課程」, so a course section that only exists for a 第二專長 cannot be picked
# by an ordinary student.  Paging is a GridView postback (Page$N), 10 rows per page.
SECEXP_URL = "https://course.sys.scu.edu.tw/currlist/SecExpQueryCls.aspx"
SECEXP_COLS = ["plan", "course_code", "name", "term_type", "credits", "weekday", "periods", "room", "teacher",
               "week_type", "group_name", "selection_no", "hours", "req_elective", "capacity", "track"]


def _aspnet_fields(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    return {i["name"]: i.get("value", "") for i in soup.find_all("input", {"type": "hidden"}) if i.get("name")}


def parse_secexp_page(html: str):
    """-> (rows, page_numbers_linked). One row per (course section, meeting time)."""
    soup = BeautifulSoup(html, "lxml")
    grid = soup.find("table", id=re.compile(r"Result_Grid$"))
    rows, pages = [], set()
    if not grid:
        return rows, pages
    for tr in grid.find_all("tr", recursive=False) or grid.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) == len(SECEXP_COLS):
            vals = [nfkc(td.get_text(" ", strip=True)) for td in tds]
            rows.append(dict(zip(SECEXP_COLS, vals)))
    for m in re.finditer(r"Page\$(\d+)", str(grid)):
        pages.add(int(m.group(1)))
    return rows, pages


def crawl_secexp(semester: str, archive_dir: Path, max_pages: int = 200) -> list:
    y, sm = parse_semester(semester)
    client = PoliteClient(archive_dir=archive_dir, min_interval=max(MIN_INTERVAL, 1.5))
    html = client.request("GET", SECEXP_URL, archive_name="secexp_form.html")
    base = {"ctl00$PlaceHolderAcademic$queryable": f"{y}{sm}", "ctl00$PlaceHolderAcademic$qrysyear": y,
            "ctl00$PlaceHolderAcademic$ddlsmester": sm, "ctl00$PlaceHolderAcademic$ddlClsid2": "",
            "ctl00$PlaceHolderAcademic$ddlClsid": ""}
    data = dict(_aspnet_fields(html), **base, **{"ctl00$PlaceHolderAcademic$btnQuery": "查 詢"})
    html = client.request("POST", SECEXP_URL, archive_name="secexp_p001.html", data=data, headers={"Referer": SECEXP_URL})
    rows, pages = parse_secexp_page(html)
    out, page = list(rows), 1
    while page + 1 in pages and page < max_pages:
        page += 1
        data = dict(_aspnet_fields(html), **base, __EVENTTARGET="ctl00$PlaceHolderAcademic$Result_Grid",
                    __EVENTARGUMENT=f"Page${page}")
        html = client.request("POST", SECEXP_URL, archive_name=f"secexp_p{page:03d}.html", data=data,
                              headers={"Referer": SECEXP_URL})
        rows, more = parse_secexp_page(html)
        out += rows; pages |= more
        print(f"  page {page}: {len(rows)} rows (total {len(out)})")
    return out


def parse_secexp_dir(d: Path) -> list:
    out = []
    for f in sorted(d.glob("secexp_p*.html")):
        out += parse_secexp_page(decode_html(f.read_bytes()))[0]
    return out


def store_secexp(con, semester: str, rows: list):
    now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    with con:
        con.execute("DELETE FROM second_expertise_courses WHERE semester=?", (semester,))
        for r in rows:
            con.execute("INSERT OR IGNORE INTO second_expertise_courses(semester, course_code, selection_no, name, track,"
                        " group_name, req_elective, credits, capacity, teacher, weekday, periods, room, week_type, scraped_at)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (semester, r["course_code"], r["selection_no"], r["name"], r["track"], r["group_name"],
                         r["req_elective"], _num(r["credits"]), _num(r["capacity"]), r["teacher"], r["weekday"],
                         r["periods"], r["room"], r["week_type"], now))

# --------------------------------------------------------------------------- CLI helpers
def select_classes(options: FormOptions, program: Optional[str], dept: Optional[str]) -> list:
    dept_labels = {(d.program_code, d.value): d.label for d in options.departments}
    out, seen = [], set()
    pcode = PROGRAM_ALIASES.get(program, program) if program else None
    for c in options.classes:
        if pcode and c.program_code != pcode:
            continue
        if dept and dept not in (dept_labels[(c.program_code, c.dept_value)], c.abbr):
            continue
        key = (c.program_code, c.value)   # same class can sit under multiple dept entries
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def codes_for_class(options: FormOptions, c: SchoolClass, year: str, sm: str) -> dict:
    prog = next(p for p in options.programs if p.code == c.program_code)
    return {"clsid1": prog.value, "clsid02": c.dept_value, "clsid34": c.value, "syear": year, "smester": sm}


def safe_name(s: str) -> str:
    return re.sub(r"[^\w\-]+", "_", nfkc(s)).strip("_")


def print_timetable(tt: dict, limit: int = 0):
    print(tt["caption"])
    n = 0
    for c in tt["courses"]:
        sessions = c["sessions"] or [{}]
        for s in sessions:
            print(" | ".join(str(x) for x in [
                s.get("weekday_label", ""), s.get("periods", ""),
                f'{s.get("start_time") or ""}-{s.get("end_time") or ""}',
                c["selection_no"], c["course_code"], c["course_name"], s.get("teacher") or c["teacher"],
                s.get("room", ""), c["credits"], c["req_elective"], c["term_type"],
                f'cap={c["capacity"]}', c["group_name"], s.get("week_type", "")]))
            n += 1
            if limit and n >= limit:
                return


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("options", help="list programs/departments/classes")
    o.add_argument("--program"); o.add_argument("--dept"); o.add_argument("--json", action="store_true")
    f = sub.add_parser("fetch", help="fetch one class timetable and store it")
    f.add_argument("--semester", help="e.g. 115-1 (default: form default)")
    g = f.add_mutually_exclusive_group(required=True)
    g.add_argument("--class-value", help="clsid34 value, e.g. '717332資科三Ｂ　'")
    g.add_argument("--profile", help="e.g. '大三 資科 B班' or JSON dict")
    f.add_argument("--no-db", action="store_true")
    c = sub.add_parser("crawl", help="full per-semester crawl (replaces that semester's data)")
    c.add_argument("--semester", required=True)
    c.add_argument("--all", action="store_true", help="crawl every class in the option list")
    c.add_argument("--program"); c.add_argument("--dept")
    c.add_argument("--limit", type=int, default=0, help="max classes (testing)")
    r = sub.add_parser("reparse", help="rebuild a semester in the DB from archived raw HTML (no network)")
    r.add_argument("--semester", required=True)
    r.add_argument("--run-dir", help="raw/<semester>/<ts> dir (default: all runs of that semester, newest wins)")
    r.add_argument("--full", action="store_true", help="replace the semester's data (use for full-crawl dirs)")
    cr = sub.add_parser("crawl-rules", help="fetch 選課限制 (selrule12.asp) for courses already in the DB")
    cr.add_argument("--semester", required=True)
    cr.add_argument("--dept", action="append", help="only courses listed on classes of this dept label (repeatable)")
    cr.add_argument("--program", help="with --dept/--code-prefix: restrict to program label, e.g. 學士班")
    cr.add_argument("--all", action="store_true", help="every course code of the semester")
    cr.add_argument("--limit", type=int, default=0)
    cr.add_argument("--code-prefix", action="append", help="only course codes starting with this prefix, e.g. P (學程課程); repeatable")
    cr.add_argument("--notes-only", action="store_true", help="no network: (re)parse 備註/組別 into course_restrictions")
    cr.add_argument("--renormalize", action="store_true", help="no network: rebuild course_restrictions from stored course_rules")
    cr.add_argument("--from-db", action="store_true", help="no network: recompute restrictions from stored course_rules + notes")
    m = sub.add_parser("map", help="map a profile to form codes")
    m.add_argument("profile"); m.add_argument("--semester")
    a = ap.parse_args(argv)

    started = dt.datetime.now().astimezone()
    if a.cmd == "reparse":
        return reparse(a.semester, a.run_dir, a.full, started)
    if a.cmd == "crawl-rules":
        return cmd_crawl_rules(a, started)
    sem_for_dir = getattr(a, "semester", None) or "current"
    run_dir = RAW_DIR / sem_for_dir / started.strftime("%Y%m%dT%H%M%S")
    client = PoliteClient(archive_dir=run_dir)
    options = parse_options(client.get_form_page())

    if a.cmd == "options":
        cls = select_classes(options, a.program, a.dept)
        if a.json:
            print(json.dumps([dataclasses.asdict(x) for x in cls], ensure_ascii=False, indent=1))
            return
        print(f"default semester on form: {options.default_year}-{options.default_semester}")
        print("programs:", [(p.value, p.label) for p in options.programs])
        dsel = [d for d in options.departments
                if (not a.program or d.program_code == PROGRAM_ALIASES.get(a.program, a.program))
                and (not a.dept or d.label == a.dept)]
        print(f"departments ({len(dsel)}):")
        for d in dsel:
            print(f"  prog={d.program_code} value={d.value!r} label={d.label} class_key={d.class_key}")
        print(f"classes ({len(cls)}):")
        for x in cls:
            print(f"  {x.value!r:24} label={x.label} grade={x.grade} section={x.section} abbr={x.abbr}")
        return

    if a.cmd == "map":
        prof = json.loads(a.profile) if a.profile.strip().startswith("{") else a.profile
        print(json.dumps(profile_to_codes(prof, options, a.semester), ensure_ascii=False))
        return

    semester = a.semester or f"{options.default_year}-{options.default_semester}"
    year, sm = parse_semester(semester)

    if a.cmd == "fetch":
        if a.profile:
            prof = json.loads(a.profile) if a.profile.strip().startswith("{") else a.profile
            codes = profile_to_codes(prof, options, semester)
        else:
            cl = next(x for x in options.classes if x.value == a.class_value or x.label == nfkc(a.class_value))
            codes = codes_for_class(options, cl, year, sm)
        html = client.post_timetable(codes, archive_name=f"class42_{safe_name(codes['clsid34'])}.html")
        tt = parse_timetable(html)
        print_timetable(tt)
        if not a.no_db:
            con = db_connect()
            run_id = replace_semester(con, semester, options, {codes["clsid34"]: tt},
                                      {"started_at": started.isoformat(timespec="seconds"),
                                       "n_requests": client.n_requests, "raw_dir": str(run_dir),
                                       "note": "single fetch"}, full=False)
            print(f"stored in {DB_PATH} (scrape_run {run_id})")
        return

    if a.cmd == "crawl":
        if not a.all and not (a.program or a.dept):
            ap.error("crawl needs --all or a --program/--dept filter")
        targets = select_classes(options, a.program, a.dept)
        if a.limit:
            targets = targets[:a.limit]
        full = a.all and not (a.program or a.dept or a.limit)
        eta = len(targets) * MIN_INTERVAL
        print(f"crawling {len(targets)} classes for {semester} (~{eta/60:.1f} min at {MIN_INTERVAL}s/req)"
              f"{' [FULL replace]' if full else ' [partial upsert]'}")
        timetables = {}
        for i, cl in enumerate(targets, 1):
            html = client.post_timetable(codes_for_class(options, cl, year, sm),
                                         archive_name=f"class42_{safe_name(cl.value)}.html")
            timetables[cl.value] = parse_timetable(html)
            print(f"  [{i}/{len(targets)}] {cl.label}: {len(timetables[cl.value]['courses'])} courses")
        con = db_connect()
        run_id = replace_semester(con, semester, options, timetables,
                                  {"started_at": started.isoformat(timespec="seconds"),
                                   "n_requests": client.n_requests, "raw_dir": str(run_dir),
                                   "note": "full crawl" if full else f"partial crawl ({len(targets)} classes)"},
                                  full=full)
        print(f"stored in {DB_PATH} (scrape_run {run_id}); raw HTML in {run_dir}")


def cmd_crawl_rules(a, started):
    con = db_connect()
    notes = {}
    for r in con.execute("""SELECT c.course_code, c.note, c.group_name, d.label FROM courses c
            JOIN class_courses cc ON cc.course_id=c.id JOIN classes cl ON cl.id=cc.class_id
            JOIN departments d ON d.id=cl.department_id WHERE c.semester=?""", (a.semester,)):
        notes.setdefault(r[0], (r[1] or "", r[2] or "", r[3]))
    if a.from_db:
        # no network: rebuild course_restrictions from the stored course_rules rows (after a parser change)
        checked = [r[0] for r in con.execute("SELECT course_code FROM course_restrictions WHERE semester=? AND rules_checked=1",
                                             (a.semester,))]
        res = {c: [] for c in checked}
        for r in con.execute("SELECT course_code, rule_code, description, phase, allow, dimension, rule_values, exceptions, raw"
                             " FROM course_rules WHERE semester=? ORDER BY id", (a.semester,)):
            res.setdefault(r[0], []).append({"rule_code": r[1], "description": r[2], "phase": r[3], "allow": r[4],
                                             "dimension": r[5], "values": json.loads(r[6] or "[]"),
                                             "exceptions": json.loads(r[7] or "[]"), "raw": r[8]})
        store_rules(con, a.semester, res, notes)
        print(f"recomputed restrictions for {len(res)} rule-checked codes (+ notes for {len(notes)} codes)")
        store_rules(con, a.semester, {}, notes)
        return
    if a.renormalize:
        res = {r[0]: [] for r in con.execute("SELECT course_code FROM course_restrictions WHERE semester=? AND rules_checked=1", (a.semester,))}
        for r in con.execute("SELECT * FROM course_rules WHERE semester=? ORDER BY id", (a.semester,)):
            res.setdefault(r["course_code"], []).append({"rule_code": r["rule_code"], "description": r["description"],
                "phase": r["phase"], "allow": r["allow"], "dimension": r["dimension"], "values": json.loads(r["rule_values"]),
                "exceptions": json.loads(r["exceptions"]), "raw": r["raw"]})
        store_rules(con, a.semester, res, notes)
        store_rules(con, a.semester, {}, notes)
        print(f"renormalized {len(res)} rule-checked codes + notes for {len(notes)} codes"); return
    if a.notes_only:
        store_rules(con, a.semester, {}, notes)
        print(f"parsed notes for {len(notes)} course codes"); return
    q = """SELECT DISTINCT c.course_code FROM courses c JOIN class_courses cc ON cc.course_id=c.id
           JOIN classes cl ON cl.id=cc.class_id JOIN departments d ON d.id=cl.department_id
           JOIN programs p ON p.id=d.program_id WHERE c.semester=?"""
    args = [a.semester]
    if a.code_prefix:
        q += " AND (%s)" % " OR ".join("c.course_code LIKE ?" for _ in a.code_prefix); args += [p + "%" for p in a.code_prefix]
    if not a.all and not a.dept and not a.code_prefix:
        raise SystemExit("crawl-rules needs --all, --dept or --code-prefix")
    if not a.all and a.dept:
        q += " AND d.label IN (%s)" % ",".join("?" * len(a.dept)); args += a.dept
    if a.program:  # with --dept or --code-prefix: only codes listed on classes of this program
        q += " AND p.label=?"; args.append(a.program)
    codes = sorted(r[0] for r in con.execute(q, args) if re.fullmatch(r"[A-Z0-9]{6}\d{2}", r[0]))
    done = {r[0] for r in con.execute("SELECT course_code FROM course_restrictions WHERE semester=? AND rules_checked=1",
                                      (a.semester,))}
    todo = [c for c in codes if c not in done]
    print(f"{len(codes)} course codes selected, {len(codes) - len(todo)} already have rules")
    run_dir = RAW_DIR / a.semester / ("rules_" + started.strftime("%Y%m%dT%H%M%S"))
    res = crawl_rules(a.semester, todo, run_dir, a.limit)
    store_rules(con, a.semester, res, notes)
    print(f"stored rules for {len(res)} codes; raw in {run_dir}")


def reparse(semester: str, run_dir: Optional[str], full: bool, started):
    dirs = [Path(run_dir)] if run_dir else sorted((RAW_DIR / semester).glob("*"))
    options, timetables = None, {}
    for d in dirs:
        form = d / "class401.asp.html"
        if form.exists():
            options = parse_options(decode_html(form.read_bytes()))
        for f in sorted(d.glob("class42_*.html")):
            tt = parse_timetable(decode_html(f.read_bytes()))
            m = re.search(r"\d+學年\s*第\s*\d學期\s*(.+?)\s*\(", tt["caption"])
            label = nfkc(m.group(1)) if m else None
            cl = next((c for c in options.classes if c.label == label), None) if options else None
            if cl:
                timetables[cl.value] = tt
    if not options:
        raise SystemExit("no class401.asp.html found in run dir(s)")
    con = db_connect()
    run_id = replace_semester(con, semester, options, timetables,
                              {"started_at": started.isoformat(timespec="seconds"), "n_requests": 0,
                               "raw_dir": ",".join(map(str, dirs)), "note": "reparse from raw"}, full=full)
    print(f"reparsed {len(timetables)} class timetables into {DB_PATH} (scrape_run {run_id})")


if __name__ == "__main__":
    main()
