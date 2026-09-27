# -*- coding: utf-8 -*-
"""學校資料的「結構化查詢工具」（直接唯讀 SQLite，不經 embedding）。

為什麼課表／課程不做 embedding？
  - 「資科三B 星期三有什麼課」需要的是**精確篩選**（班級＝資科三B AND 星期＝3），
    向量相似度只會找到「長得像」的課，可能漏掉或多出，還會把 3,432 門課的雜訊放進索引。
  - SQL 一次就拿到完整、正確的列表；答案直接用資料排版，不經 LLM → 不會編造時間或教室。
  → 規則：**有明確欄位可以篩的資料用 SQL 工具；沒有固定格式的文字（公告、行事曆說明、政策）才用向量檢索。**

資料來源：scu-backend 的 db.sqlite3，以 `mode=ro` 唯讀開啟（絕不寫入、不改 scu-backend）。
選課時段的推算移植自 scu-backend/enrollment/windows.py（同樣規則，改成純 SQL 版）。
"""
from __future__ import annotations

import contextvars
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from config import DEFAULT_PROFILE, SCU_DB, SCU_DEMO_NOW, SCU_SEMESTER

TZ = ZoneInfo("Asia/Taipei")
WD = "一二三四五六日"
PERIOD_ORDER = "1234E56789ABCD"
PERIOD_TIMES = {"1": ("08:10", "09:00"), "2": ("09:10", "10:00"), "3": ("10:10", "11:00"), "4": ("11:10", "12:00"),
                "E": ("12:10", "13:00"), "5": ("13:10", "14:00"), "6": ("14:10", "15:00"), "7": ("15:10", "16:00"),
                "8": ("16:10", "17:00"), "9": ("17:10", "18:00"), "A": ("18:25", "19:15"), "B": ("19:20", "20:10"),
                "C": ("20:20", "21:10"), "D": ("21:15", "22:05")}
CN_NUM = {"1": "一", "2": "二", "3": "三", "4": "四", "5": "五", "6": "六", "7": "七"}

_local = threading.local()


def db() -> sqlite3.Connection:
    """每個執行緒一條唯讀連線（ThreadingHTTPServer 會用多執行緒）。"""
    con = getattr(_local, "con", None)
    if con is None:
        uri = "file:" + SCU_DB.as_posix() + "?mode=ro"
        con = sqlite3.connect(uri, uri=True, check_same_thread=False)
        con.row_factory = sqlite3.Row
        _local.con = con
    return con


def q_all(sql: str, args: tuple = ()) -> list[dict]:
    return [dict(r) for r in db().execute(sql, args)]


# ---------------------------------------------------------------------------
# 現在時間、學生
# ---------------------------------------------------------------------------
def now_is_demo() -> bool:
    v = (SCU_DEMO_NOW or "").strip().lower()
    return v not in ("", "real")


def now_phrase() -> str:
    return "示範現在時間" if now_is_demo() else "現在時間"


_request_now: contextvars.ContextVar[datetime | None] = contextvars.ContextVar("trade_rag_now", default=None)


def set_request_now(when: datetime | None):
    """這一輪請求用的時鐘（入口站傳入的示範日）。用完要 reset。"""
    return _request_now.set(when)


def reset_request_now(token) -> None:
    _request_now.reset(token)


def now() -> datetime:
    pinned = _request_now.get()
    if pinned is not None:
        return pinned
    v = (SCU_DEMO_NOW or "").strip()
    if not v or v.lower() == "real":
        return datetime.now(TZ)
    d = datetime.fromisoformat(v.replace(" ", "T"))
    return d if d.tzinfo else d.replace(tzinfo=TZ)


def _fmt_day(d: date) -> str:
    return f"{d.year}/{d.month}/{d.day}（星期{WD[d.weekday()]}）"


def clock_brief() -> str:
    """給語言模型的時鐘。小模型不會自己看系統時間，也不能可靠地心算「下週一」。"""
    ref = now()
    base = ref.date()
    kind = "示範時間，與課表／行事曆同一套時鐘" if now_is_demo() else "台北系統時間"
    this_mon = base - timedelta(days=base.isoweekday() - 1)
    next_mon = this_mon + timedelta(days=7)
    return "\n".join([
        f"現在時間：{ref:%Y/%m/%d}（星期{WD[ref.weekday()]}）{ref:%H:%M}（{kind}）。",
        "回答「今天／明天／下週／幾點」時只能用下面這張表，不要用訓練資料裡的日期，也不要自己另外換算。",
        f"今天＝{_fmt_day(base)}；明天＝{_fmt_day(base + timedelta(days=1))}；"
        f"後天＝{_fmt_day(base + timedelta(days=2))}；昨天＝{_fmt_day(base - timedelta(days=1))}。",
        f"這週一～日：{_fmt_day(this_mon)}～{_fmt_day(this_mon + timedelta(days=6))}。",
        f"下週一～日：{_fmt_day(next_mon)}～{_fmt_day(next_mon + timedelta(days=6))}。",
    ])


def question_clock_hint(q: str) -> str:
    """問句裡若有今天／下週一／10/9，先算好再交給模型。"""
    d, _, txt = find_day(q or "", now())
    if not d or not txt:
        return ""
    return f"問句裡的時間「{txt}」＝{_fmt_day(d)}。請用這個日期，不要另外換算。"


_CLOCK_Q = re.compile(
    r"(現在幾點|現在時間|目前幾點|今天幾號|今天是幾號|今天星期幾|今天是星期幾|今天禮拜幾|"
    r"明天幾號|明天是幾號|明天星期幾|後天幾號|昨天幾號|"
    r"下(?:個)?(?:星期|週|周|禮拜)[一二三四五六日天](?:是)?(?:幾號|星期幾|禮拜幾)|"
    r"這(?:個)?(?:星期|週|周|禮拜)[一二三四五六日天](?:是)?(?:幾號|星期幾))"
)


def clock_question_answer(q: str) -> str | None:
    """整句只在問現在幾點／某天是幾號 → 直接用時鐘，不進模型、也不進行事曆檢索。"""
    s = re.sub(r"[\s，。！？、,.!?呢啊呀嗎了]", "", q or "")
    s = re.sub(r"^(請問|問一下|告訴我)", "", s)
    m = _CLOCK_Q.search(s)
    if not m:
        return None
    if (s[:m.start()] + s[m.end():]).strip():
        return None
    ref = now()
    d, _, txt = find_day(q, ref)
    if d is None:
        d, txt = ref.date(), "現在"
    if any(k in s for k in ("幾點", "現在時間", "目前幾點")):
        return f"{txt}是 {_fmt_day(d)} {ref:%H:%M}（台北）。".replace("） ", "）")
    return f"{txt}是 {_fmt_day(d)}。"


def get_profile(override: dict | None = None) -> dict:
    """預設學生（config.DEFAULT_PROFILE）＋ API 傳入的覆寫欄位。"""
    p = dict(DEFAULT_PROFILE)
    for k, v in (override or {}).items():
        if v not in (None, ""):
            p[k] = v
    try:
        p["grade"] = int(p.get("grade") or 0)
    except (TypeError, ValueError):
        p["grade"] = 0
    p["cls"] = str(p.get("cls") or "").upper()
    lab = class_label_of(p)
    p["classLabel"] = lab
    # 只有預設示範學生（學號相同）才有「個人課表」（scu-backend enrollment 表）
    demo = q_all("SELECT student_id, user_id FROM accounts_studentprofile WHERE is_demo=1 LIMIT 1")
    p["_user_id"] = demo[0]["user_id"] if demo and str(demo[0]["student_id"]) == str(p.get("student_id")) else None
    return p


def class_label_of(p: dict) -> str | None:
    rows = q_all(
        """SELECT sc.label FROM timetable_schoolclass sc
           JOIN timetable_department d ON d.id = sc.department_id
           JOIN timetable_program pr ON pr.id = d.program_id
           WHERE sc.semester=? AND d.label=? AND pr.label=? AND sc.grade=? AND (sc.section=? OR sc.section='')
           ORDER BY sc.section DESC LIMIT 1""",
        (SCU_SEMESTER, p.get("dept"), p.get("program"), p.get("grade"), p.get("cls")),
    )
    return rows[0]["label"] if rows else None


# ---------------------------------------------------------------------------
# 從問題文字找班級、星期、日期
# ---------------------------------------------------------------------------
_FW = str.maketrans("ＡＢＣＤＥＦａｂｃｄｅｆ０１２３４５６７８９", "ABCDEFabcdef0123456789")
_class_labels: list[str] | None = None


def all_class_labels() -> list[str]:
    global _class_labels
    if _class_labels is None:
        rows = q_all("SELECT DISTINCT label FROM timetable_schoolclass WHERE semester=?", (SCU_SEMESTER,))
        _class_labels = sorted({r["label"] for r in rows if r["label"]}, key=len, reverse=True)
    return _class_labels


def normalize_text(q: str) -> str:
    q = (q or "").translate(_FW)
    # 「資科3b」→「資科三B」
    q = re.sub(r"([\u4e00-\u9fff])([1-7])([A-Da-d])?(?![0-9])",
               lambda m: m.group(1) + CN_NUM[m.group(2)] + (m.group(3) or "").upper(), q)
    q = re.sub(r"([一二三四五六七])([a-d])(?![a-z])", lambda m: m.group(1) + m.group(2).upper(), q)
    return q


def find_class_label(q: str) -> str | None:
    """問題裡提到的班級，例如「資科三B」；也接受「資料科學系三年級B班」。"""
    t = normalize_text(q)
    for lab in all_class_labels():
        if len(lab) >= 3 and lab in t:
            return lab
    m = re.search(r"([\u4e00-\u9fff]{2,10}系)\s*([一二三四五六七])\s*年級\s*([A-D])?\s*班?", t)
    if m:
        rows = q_all(
            """SELECT sc.label FROM timetable_schoolclass sc JOIN timetable_department d ON d.id=sc.department_id
               WHERE sc.semester=? AND d.label=? AND sc.grade=? AND (sc.section=? OR ?='') LIMIT 1""",
            (SCU_SEMESTER, m.group(1), "一二三四五六七".index(m.group(2)) + 1, m.group(3) or "", m.group(3) or ""),
        )
        if rows:
            return rows[0]["label"]
    return None


WEEKDAY_RE = re.compile(r"(?:星期|週|周|禮拜|礼拜)([一二三四五六日天1-7])")
NEXT_WEEKDAY_RE = re.compile(r"下(?:個)?(?:星期|週|周|禮拜|礼拜)([一二三四五六日天1-7])")
THIS_WEEKDAY_RE = re.compile(r"(?:這|本)(?:個)?(?:星期|週|周|禮拜|礼拜)([一二三四五六日天1-7])")
# 不用連字號當分隔，避免把學期「115-1」當成 5 月 1 日
YMD_RE = re.compile(r"(?:(\d{4})\s*年\s*)?(\d{1,2})\s*月\s*(\d{1,2})\s*日?")
SLASH_DATE_RE = re.compile(r"(?:(\d{4})/)?(\d{1,2})/(\d{1,2})(?!\d)")
ISO_DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")


def _wd_from_token(ch: str) -> int:
    if ch in "日天":
        return 7
    if ch in "一二三四五六":
        return "一二三四五六".index(ch) + 1
    return int(ch)


def _date_on_week(base: date, wd: int, *, weeks_ahead: int = 0) -> date:
    monday = base - timedelta(days=base.isoweekday() - 1) + timedelta(days=7 * weeks_ahead)
    return monday + timedelta(days=wd - 1)


def _ymd_from_parts(year: int | None, month: int, day: int, ref: date) -> date | None:
    try:
        if year:
            return date(year, month, day)
        cand = date(ref.year, month, day)
    except ValueError:
        return None
    if (ref - cand).days > 120:
        try:
            cand = date(ref.year + 1, month, day)
        except ValueError:
            return None
    return cand


def find_day(q: str, ref: datetime) -> tuple[date | None, int | None, str]:
    """回傳 (日期 或 None, 星期幾 1–7 或 None, 說明文字)。"""
    t = q or ""
    base = ref.date()
    for k, off in (("大後天", 3), ("後天", 2), ("明天", 1), ("明日", 1), ("昨天", -1), ("今天", 0), ("今日", 0),
                   ("等一下", 0), ("等等", 0), ("現在", 0), ("待會", 0)):
        if k in t:
            d = base + timedelta(days=off)
            return d, d.isoweekday(), k
    m = NEXT_WEEKDAY_RE.search(t)
    if m:
        wd = _wd_from_token(m.group(1))
        d = _date_on_week(base, wd, weeks_ahead=1)
        return d, wd, f"下星期{WD[wd - 1]}"
    m = THIS_WEEKDAY_RE.search(t)
    if m:
        wd = _wd_from_token(m.group(1))
        d = _date_on_week(base, wd, weeks_ahead=0)
        return d, wd, f"這星期{WD[wd - 1]}"
    m = WEEKDAY_RE.search(t)
    if m:
        wd = _wd_from_token(m.group(1))
        # 本週（週一開始）的那一天，用來判斷單雙週
        d = _date_on_week(base, wd, weeks_ahead=0)
        return d, wd, f"星期{WD[wd - 1]}"
    for pat in (ISO_DATE_RE, YMD_RE, SLASH_DATE_RE):
        m = pat.search(t)
        if not m:
            continue
        year = int(m.group(1)) if m.group(1) else None
        month, day = int(m.group(2)), int(m.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31:
            d = _ymd_from_parts(year, month, day, base)
            if d:
                return d, d.isoweekday(), f"{d.year}/{d.month}/{d.day}"
    return None, None, ""


# ---------------------------------------------------------------------------
# 學期週次、放假
# ---------------------------------------------------------------------------
def semester_start() -> date | None:
    rows = q_all(
        """SELECT MIN(start_date) d FROM events_event WHERE semester=? AND is_active=1
           AND (title LIKE '%開學日%' OR title='上課開始')""", (SCU_SEMESTER,))
    return date.fromisoformat(rows[0]["d"]) if rows and rows[0]["d"] else None


def week_no(d: date) -> int | None:
    s = semester_start()
    if not s or d < s:
        return None
    return (d - s).days // 7 + 1


def week_type_applies(wk: str, n: int | None) -> bool | None:
    """單／雙週、前／後 9 週；n 未知時回 None（不確定）。"""
    if not wk:
        return True
    if n is None:
        return None
    return {"單": n % 2 == 1, "雙": n % 2 == 0, "前": n <= 9, "後": n > 9}.get(wk, True)


def holidays_on(d: date) -> list[dict]:
    iso = d.isoformat()
    return q_all(
        """SELECT id, title, start_date, end_date, source_name FROM events_event
           WHERE is_active=1 AND category='放假' AND source_name='scu_calendar_ics'
           AND start_date<=? AND COALESCE(end_date, start_date)>=?
           AND title NOT LIKE '%暑假%' AND title NOT LIKE '%寒假%'""", (iso, iso))


# ---------------------------------------------------------------------------
# 課程與上課時段
# ---------------------------------------------------------------------------
@dataclass
class Slot:
    course_id: int
    code: str
    cid: str
    name: str
    teacher: str
    credits: float
    req: str
    offering_class: str
    weekday: int
    periods: str
    start: str
    end: str
    week_type: str
    room: str
    note: str


def _slots_where(where: str, args: tuple) -> list[Slot]:
    rows = q_all(
        f"""SELECT co.id course_id, co.selection_no code, co.course_code cid, co.name, co.teacher, co.credits,
                   co.offering_class, co.note, s.weekday, s.periods, s.start_time, s.end_time, s.week_type, s.room,
                   {"cc.req_elective" if "cc." in where else "''"} req
            FROM timetable_course co
            {"JOIN timetable_classcourse cc ON cc.course_id=co.id JOIN timetable_schoolclass sc ON sc.id=cc.school_class_id" if "sc." in where else ""}
            LEFT JOIN timetable_coursesession s ON s.course_id=co.id
            WHERE co.semester=? AND {where}""", (SCU_SEMESTER,) + args)
    out = []
    for r in rows:
        out.append(Slot(r["course_id"], r["code"] or "", r["cid"] or "", r["name"], " ".join((r["teacher"] or "").split()),
                        r["credits"] or 0, r["req"] or "", r["offering_class"] or "", r["weekday"] or 0,
                        r["periods"] or "", (r["start_time"] or "")[:5], (r["end_time"] or "")[:5],
                        r["week_type"] or "", r["room"] or "", r["note"] or ""))
    return out


def class_slots(label: str) -> list[Slot]:
    return _slots_where("cc.course_id=co.id AND sc.label=? AND sc.semester=?", (label, SCU_SEMESTER))


def my_slots(profile: dict) -> tuple[list[Slot], str]:
    """個人課表：示範學生讀 enrollment 表；其他學生退回班級課表的必修課。"""
    uid = profile.get("_user_id")
    if uid:
        keys = [r["course_key"] for r in q_all(
            "SELECT course_key FROM enrollment_enrollment WHERE user_id=? AND semester=?", (uid, SCU_SEMESTER))]
        out: list[Slot] = []
        for k in keys:
            if "@" in k:
                cid, ocls = k.split("@", 1)
                out += _slots_where("co.course_code=? AND co.offering_class=?", (cid, ocls))
            else:
                out += _slots_where("co.selection_no=?", (k,))
        return out, "我的課表（scu-backend enrollment，示範學生）"
    lab = profile.get("classLabel")
    if not lab:
        return [], "找不到這位學生的班級"
    return [s for s in class_slots(lab) if s.req == "必"], f"{lab} 班級課表的必修課（沒有個人選課資料）"


def fmt_slot(s: Slot, with_day: bool = False) -> str:
    day = f"星期{WD[s.weekday - 1]} " if with_day and s.weekday else ""
    ps = s.periods or ""
    per = (f"第{ps[0]}–{ps[-1]}節" if len(ps) > 1 else f"第{ps}節") if ps else "時間未定"
    tm = f" {s.start}–{s.end}" if s.start else ""
    wk = f"（{s.week_type}週）" if s.week_type in ("單", "雙") else (f"（{s.week_type}9週）" if s.week_type in ("前", "後") else "")
    room = f"｜教室 {s.room}" if s.room else ""
    teacher = f"｜{s.teacher}" if s.teacher else ""
    code = f"｜選課編號 {s.code}" if s.code else ""
    req = f"〔{s.req}修〕" if s.req in ("必", "選") else ""
    note = f"｜{s.note}" if s.note else ""
    return f"{day}{per}{tm}{wk} {s.name}{req}{teacher}{room}{code}{note}"


def sort_slots(ss: list[Slot]) -> list[Slot]:
    def key(s: Slot):
        p = PERIOD_ORDER.index(s.periods[0]) if s.periods and s.periods[0] in PERIOD_ORDER else 99
        return (s.weekday or 9, p, s.name)
    return sorted(ss, key=key)


_course_names: list[str] | None = None


def all_course_names() -> list[str]:
    global _course_names
    if _course_names is None:
        rows = q_all("SELECT DISTINCT name FROM timetable_course WHERE semester=?", (SCU_SEMESTER,))
        _course_names = sorted({r["name"] for r in rows if r["name"] and len(r["name"]) >= 3},
                               key=len, reverse=True)
    return _course_names


def find_course_names(q: str) -> list[str]:
    t = normalize_text(q)
    found = []
    for n in all_course_names():
        if n in t and not any(n in f for f in found):
            found.append(n)
    return found[:3]


def course_offerings(name: str) -> list[Slot]:
    return _slots_where("co.name=?", (name,))


# ---------------------------------------------------------------------------
# 行事曆、公告
# ---------------------------------------------------------------------------
def events_all() -> list[dict]:
    """去重後的行事曆（ICS 與 PDF 內容重複，只留 ICS；選課時間表、公告擷取的日期也保留）。"""
    rows = q_all(
        """SELECT id, source_name, title, category, start_date, end_date, raw_text, note, source_url, semester
           FROM events_event WHERE is_active=1 ORDER BY start_date, id""")
    seen, out = set(), []
    pri = {"scu_calendar_ics": 0, "scu_course_timetable": 1, "announcement_title": 2, "scu_calendar_pdf": 3}
    for r in sorted(rows, key=lambda r: (pri.get(r["source_name"], 9), r["id"])):
        k = (r["title"].strip(), r["start_date"])
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    out.sort(key=lambda r: (r["start_date"], r["id"]))
    return out


SOURCE_TEXT = {"scu_calendar_ics": "東吳大學行事曆（教務處 ICS）", "scu_calendar_pdf": "115 學年行事曆 PDF",
               "scu_course_timetable": "學士班網路選課註冊時間表", "announcement_title": "校園公告標題擷取"}


def fmt_date(iso: str | None) -> str:
    if not iso:
        return ""
    d = date.fromisoformat(iso)
    return f"{d.year}/{d.month}/{d.day}（{WD[d.weekday()]}）"


def fmt_event(e: dict) -> str:
    rng = fmt_date(e["start_date"])
    if e.get("end_date") and e["end_date"] != e["start_date"]:
        rng += " ～ " + fmt_date(e["end_date"])
    return f"{rng} {e['title']}"


def events_upcoming(ref: datetime, category: str | None = None, keyword: str | None = None, limit: int = 5) -> list[dict]:
    today = ref.date().isoformat()
    out = []
    for e in events_all():
        if (e.get("end_date") or e["start_date"]) < today:
            continue
        if category and e["category"] != category:
            continue
        if keyword and keyword not in e["title"]:
            continue
        out.append(e)
    if category is None and not keyword:
        cat_pri = {"放假": 0, "考試": 1, "選課": 2, "繳費": 3}
        out.sort(key=lambda e: (
            e["start_date"] < today,
            1 if e.get("source_name") == "announcement_title" else 0,
            cat_pri.get(e.get("category") or "", 5),
            e["start_date"],
            e["id"],
        ))
    return out[:limit]


def events_search(keyword: str, ref: datetime | None = None, limit: int = 5) -> list[dict]:
    """依標題／原文關鍵字找行事曆（含已過的，例如剛過的教師節）。"""
    kw = (keyword or "").strip()
    if not kw:
        return []
    rows = [e for e in events_all() if kw in (e.get("title") or "") or kw in (e.get("raw_text") or "")]
    if ref:
        today = ref.date()

        def _key(e: dict) -> tuple:
            start = date.fromisoformat(e["start_date"])
            end = date.fromisoformat(e["end_date"] or e["start_date"])
            past = 1 if end < today else 0
            return (past, abs((start - today).days), e["id"])

        rows.sort(key=_key)
    return rows[:limit]


def news_latest(limit: int = 5, keywords: list[str] | None = None) -> list[dict]:
    rows = q_all("SELECT title, date, unit, category, tag, url FROM events_announcement ORDER BY date DESC, id ASC")
    if keywords:
        rows = [r for r in rows if any(k in r["title"] or k == r["tag"] for k in keywords)]
    return rows[:limit]


# ---------------------------------------------------------------------------
# 選課時段（移植 scu-backend/enrollment/windows.py，規則相同）
# ---------------------------------------------------------------------------
COLLEGE_ALIASES = {
    "巨量資料管理學院": ["巨量學院", "巨量"], "理學院": ["理學院"], "商學院": ["商學院"],
    "人文社會學院": ["人社院", "人社學院"], "外國語文學院": ["外語學院"], "法學院": ["法學院", "法律系"],
}
ALL_SCOPE_TOKENS = sorted({t for v in COLLEGE_ALIASES.values() for t in v}, key=len, reverse=True)
SKIP_WORDS = ("人工加選", "結果查詢", "列印", "導師輔導", "公告選課", "線上登記", "抵免")
TIME_RE = re.compile(r"(\d{1,2})\s*[:：]\s*(\d{2})")
SCOPE_TEXT = {"all": "全部課程", "major": "學系專業課程", "general": "共通科目（通識、體育等）", "second": "第二專長課程"}


@dataclass
class Window:
    title: str
    start: datetime
    end: datetime
    kind: str
    phase: str
    scope: str
    applies: bool
    why_not: str
    source: str


def fmt_dt(d: datetime, is_end: bool = True) -> str:
    if is_end and d.hour == 0 and d.minute == 0:
        p = d - timedelta(minutes=1)
        return f"{p.month}/{p.day}（{WD[p.weekday()]}）24:00"
    return f"{d.month}/{d.day}（{WD[d.weekday()]}）{d:%H:%M}"


def fmt_range(a: datetime, b: datetime) -> str:
    return f"{fmt_dt(a, False)} ～ {fmt_dt(b)}"


def _times(raw: str):
    parts = (raw or "").split("|")
    mid = parts[1] if len(parts) >= 3 else ""
    ts = [(int(h), int(m)) for h, m in TIME_RE.findall(mid)]
    return (ts[0] if ts else (0, 0)), (ts[1] if len(ts) >= 2 else (24, 0))


def _at(d: date, hm) -> datetime:
    return datetime.combine(d, time(0, 0), tzinfo=TZ) + timedelta(hours=hm[0], minutes=hm[1])


def _classify(title: str):
    if any(w in title for w in SKIP_WORDS):
        return None
    if "確認選課清單" in title:
        return "confirm", "確認清單", "all"
    if "即時退選" in title:
        return "drop", "退選", "all"
    if "初選" in title:
        return "select", "初選", "all"
    if "第二專長" in title and "共通" not in title and "加退選" not in title:
        return "select", "第二專長選課", "second"
    if "加退選" in title or "選課" in title:
        phase = "新生選課" if "新生" in title else "加退選"
        if "共通科目" in title:
            scope = "general"
        elif "專業課程" in title and "全校所有課程" not in title:
            scope = "major"
        else:
            scope = "all"
        return "select", phase, scope
    return None


def _applies(title: str, student: dict, scope: str):
    if "新生" in title and int(student.get("grade") or 0) != 1:
        return False, "只限新生"
    if scope == "second":
        return False, "只限第二專長課程"
    tokens = [t for t in ALL_SCOPE_TOKENS if t in title]
    if tokens:
        mine = COLLEGE_ALIASES.get(student.get("college") or "", []) + [student.get("dept") or ""]
        if not any(m and m in title for m in mine):
            return False, "只限" + "、".join(tokens) + "的學生"
    return True, ""


def selection_windows(student: dict) -> list[Window]:
    rows = q_all(
        """SELECT title, start_date, end_date, raw_text FROM events_event WHERE category='選課' AND is_active=1
           AND semester=? AND source_name='scu_course_timetable' ORDER BY start_date, id""", (SCU_SEMESTER,))
    source = "學士班網路選課註冊時間表"
    if not rows:
        rows = q_all(
            """SELECT title, start_date, end_date, raw_text FROM events_event WHERE category='選課' AND is_active=1
               AND semester=? AND source_name='scu_calendar_ics' ORDER BY start_date, id""", (SCU_SEMESTER,))
        source = "東吳大學行事曆"
    out = []
    for e in rows:
        c = _classify(e["title"])
        if not c:
            continue
        kind, phase, scope = c
        (sh, sm), (eh, em) = _times(e["raw_text"])
        sd = date.fromisoformat(e["start_date"])
        ed = date.fromisoformat(e["end_date"]) if e["end_date"] else sd
        start, end = _at(sd, (sh, sm)), _at(ed, (eh, em))
        if end <= start:
            end = _at(ed, (24, 0))
        ok, why = _applies(e["title"], student, scope)
        out.append(Window(e["title"], start, end, kind, phase, scope, ok, why, source))
    out.sort(key=lambda w: (w.start, w.end))
    return out


def window_status(student: dict, at: datetime) -> dict:
    wins = selection_windows(student)
    usable = [w for w in wins if w.applies]
    active = [w for w in usable if w.start <= at < w.end]
    select = [w for w in active if w.kind == "select"]
    drop = [w for w in active if w.kind == "drop"]
    confirm = [w for w in active if w.kind == "confirm"]
    upcoming = [w for w in usable if w.start > at and w.kind in ("select", "drop")]
    ended = [w for w in usable if w.end <= at and w.kind in ("select", "drop")]
    nxt, last = (upcoming[0] if upcoming else None), (ended[-1] if ended else None)
    now_txt = f"{at:%Y/%m/%d %H:%M}"
    if select:
        cur = select[0]
        reason = f"現在是「{cur.title}」（{fmt_range(cur.start, cur.end)}），可以加選與退選"
        scopes = sorted({w.scope for w in select})
        if "all" not in scopes:
            reason += "；這個階段只開放" + "、".join(SCOPE_TEXT[s] for s in scopes)
    elif drop:
        cur = drop[0]
        reason = f"現在是「{cur.title}」（{fmt_range(cur.start, cur.end)}），只能退選、不能加選"
    else:
        reason = f"目前（{now_phrase()} {now_txt}）不是選課時段，不能加選、退選或送出選課。"
        if confirm:
            reason += f"現在是「{confirm[0].title}」（{fmt_range(confirm[0].start, confirm[0].end)}），只能確認選課清單。"
        if last:
            reason += f"上一個選課時段「{last.title}」已於 {fmt_dt(last.end)} 結束。"
        reason += f"下一個選課時段：「{nxt.title}」{fmt_range(nxt.start, nxt.end)}。" if nxt else "下一個選課時段尚未公布。"
    upcoming_confirm = [w for w in usable if w.kind == "confirm" and w.start > at]
    return {"now": at, "open": bool(select or drop), "canAdd": bool(select), "canDrop": bool(select or drop),
            "reason": reason, "windows": wins, "next": nxt, "last": last, "confirm_next": upcoming_confirm[:1],
            "confirm_now": confirm[:1]}
