"""timetable/catalog.py — 把資料庫裡的課程整理成「前端要的樣子」，並放在記憶體快取

為什麼要快取？全校 3,400 多門課 × 上課時段 × 班級課表，每個 request 都重查資料庫很浪費。
這裡第一次用到時一次讀進來（5 個查詢），之後直接用記憶體裡的結果；
資料庫內容變了（重新匯入／爬蟲）→ version 不同 → 自動重建。

提供：
  get_catalog(semester)       → Catalog 物件
  Catalog.course_json(c, ...) → 單門課的 JSON（欄位同前端 data-source.js 的 decodeCourse）
  Catalog.courses_bundle()    → 與 js/real-courses.js 的 SCU.REAL_COURSES 完全相同的結構
  Catalog.classes_bundle()    → 與 js/real-classes.js 的 SCU.REAL_CLASSES 完全相同的結構
"""
import json
import math
import threading
import unicodedata

from django.db.models import Count, Max

from .eligibility import can_take
from .models import (GENERAL_DEPTS, PERIOD_TIMES, ClassCourse, Course, CourseRestriction, CourseSession,
                     Department, Program, SchoolClass, ScrapeRun)

_lock = threading.Lock()
_cache = {}


def nfkc(s):
    return unicodedata.normalize("NFKC", str(s or "")).strip()


def fake_enrolled(code, cap):
    """已選人數（示範）：學校沒有公開即時人數 → 依課程代碼產生固定假數字，約 1/9 額滿。
    演算法與前端 data-source.js 的 fakeEnrolled() 完全相同，前後端數字一致。"""
    if not cap:
        return 0
    h = 0
    for ch in code:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    if h % 9 == 0:
        return cap
    return min(cap, math.floor(cap * (0.35 + (h % 60) / 100) + 0.5))


def _num(x):
    if x is None:
        return 0
    f = float(x)
    return int(f) if f.is_integer() else f


def special_of(extra):
    """特殊課程標記（第二專長、進修學士班、學程…）：爬蟲新版才有的欄位，放在 Course.extra。
    輸出格式同前端 real-courses.js 第 16 欄：[kind, reason, [[kind, names[], blocking]]]；沒有則 None"""
    if not extra or not extra.get("special_track"):
        return None
    det = extra.get("special_detail") or {}
    if isinstance(det, str):
        try:
            det = json.loads(det)
        except ValueError:
            det = {}
    tags = [[t.get("kind", ""), t.get("names") or [], 1 if t.get("blocking") else 0] for t in det.get("tags", [])]
    return [extra["special_track"], extra.get("special_reason") or "", tags]


def _version(semester):
    agg = Course.objects.filter(semester=semester).aggregate(n=Count("id"), m=Max("id"))
    r = CourseRestriction.objects.filter(semester=semester).aggregate(n=Count("pk"), m=Max("scraped_at"))
    run = ScrapeRun.objects.filter(semester=semester).aggregate(m=Max("id"))
    return (agg["n"], agg["m"], r["n"], str(r["m"]), run["m"])


def get_catalog(semester):
    v = _version(semester)
    with _lock:
        cat = _cache.get(semester)
        if cat is None or cat.version != v:
            cat = Catalog(semester, v)
            _cache[semester] = cat
        return cat


def clear_cache():
    with _lock:
        _cache.clear()


class Catalog:
    def __init__(self, semester, version):
        self.semester, self.version = semester, version
        self.periods = [{"p": i + 1, "label": p[0], "t": f"{p[1]}–{p[2]}"} for i, p in enumerate(PERIOD_TIMES)]
        self._build()

    # ------------------------------------------------------------------ build
    def _build(self):
        sem = self.semester
        progs = list(Program.objects.filter(semester=sem).order_by("code").values("id", "code", "label"))
        prog_by_id = {p["id"]: p for p in progs}
        self.programs = [{"code": p["code"], "label": p["label"]} for p in progs]

        self.depts, dept_by_id = [], {}
        for d in Department.objects.filter(semester=sem).order_by("id").values("id", "program_id", "label"):
            p = prog_by_id.get(d["program_id"], {"code": "", "label": ""})
            obj = {"id": d["id"], "i": len(self.depts), "program": p["label"], "programCode": p["code"],
                   "label": d["label"], "general": d["label"] in GENERAL_DEPTS, "classIds": []}
            self.depts.append(obj)
            dept_by_id[d["id"]] = obj

        self.classes, self.class_by_id = [], {}
        for c in SchoolClass.objects.filter(semester=sem).order_by("id").values(
                "id", "department_id", "label", "grade", "section", "timetable_scraped_at"):
            d = dept_by_id[c["department_id"]]
            obj = {"id": c["id"], "i": len(self.classes), "dept": d, "label": c["label"], "grade": c["grade"],
                   "section": c["section"] or "", "scraped": bool(c["timetable_scraped_at"]), "items": []}
            self.classes.append(obj)
            self.class_by_id[c["id"]] = obj
            d["classIds"].append(c["id"])

        restr = {r.course_code: r.to_front() for r in CourseRestriction.objects.filter(semester=sem)}
        sessions = {}
        for s in CourseSession.objects.filter(course__semester=sem).order_by("id"):
            sessions.setdefault(s.course_id, []).append(s)

        self.courses, self.by_code, by_id = [], {}, {}
        for c in Course.objects.filter(semester=sem).order_by("course_code", "selection_no", "id"):
            slots, tba = [], False
            for s in sessions.get(c.id, []):
                runs, unknown = s.slot_runs()
                tba = tba or unknown or not runs
                for st, en in runs:
                    slots.append({"day": s.weekday or 0, "start": st, "end": en, "room": s.room or "",
                                  "wk": s.week_type or "",
                                  "teacher": s.teacher if s.teacher and s.teacher != c.teacher else ""})
            rooms = []
            for s in slots:
                if s["room"] and s["room"] not in rooms:
                    rooms.append(s["room"])
            cap = c.capacity or 0
            obj = {"idx": len(self.courses), "id": c.id, "code": c.offering_key, "no": c.selection_no or "",
                   "cid": c.course_code, "name": c.name, "teacher": c.teacher or "", "credits": _num(c.credits),
                   "hours": _num(c.hours), "cap": cap, "unlimited": not cap, "term": c.term_type or "",
                   "group": c.group_name or "", "note": c.note or "", "ocls": nfkc(c.offering_class),
                   "slots": slots, "restr": restr.get(c.course_code), "tba": (tba and not slots) or not slots,
                   "tbaFlag": 1 if tba and not slots else 0, "placeholder": not c.selection_no,
                   "room": "、".join(rooms) or "—", "enrolledBase": fake_enrolled(c.offering_key, cap),
                   "extra": c.extra or {}, "special": special_of(c.extra),
                   "specialBlocking": bool((c.extra or {}).get("special_blocking")), "listings": []}
            self.courses.append(obj)
            self.by_code[c.offering_key] = obj
            by_id[c.id] = obj

        for cc in ClassCourse.objects.filter(course__semester=sem).values("school_class_id", "course_id", "req_elective"):
            co, cl = by_id.get(cc["course_id"]), self.class_by_id.get(cc["school_class_id"])
            if co and cl:
                cl["items"].append([co["idx"], cc["req_elective"] or ""])
        for cl in self.classes:
            cl["items"].sort()
            for ci, req in cl["items"]:
                self.courses[ci]["listings"].append({"cls": cl, "req": req})
        for co in self.courses:
            prim = next((l for l in co["listings"] if l["cls"]["label"] == co["ocls"]), None) or \
                (co["listings"][0] if co["listings"] else None)
            co["primary"] = prim
            co["dept"] = prim["cls"]["dept"]["label"] if prim else ""
            co["program"] = prim["cls"]["dept"]["program"] if prim else ""
            co["grade"] = prim["cls"]["grade"] if prim else None
            co["clsLabel"] = prim["cls"]["label"] if prim else co["ocls"]
            co["general"] = bool(prim and prim["cls"]["dept"]["general"])

        run = (ScrapeRun.objects.filter(semester=sem, status="ok").order_by("-is_full", "-id").first())
        scraped = (run.finished_at or run.started_at).date().isoformat() if run else ""
        n_chk = sum(1 for r in restr.values() if r.get("chk"))
        n_restr = sum(1 for r in restr.values() if any(k in r for k in ("g", "min", "d", "p", "c", "dn")))
        n_special = {}
        for co in self.courses:
            if co["special"]:
                n_special[co["special"][0]] = n_special.get(co["special"][0], 0) + 1
        n_special = dict(sorted(n_special.items(), key=lambda kv: -kv[1]))
        self.meta = {"semester": sem, "scrapedAt": scraped, "source": "東吳大學公開課表",
                     "nCourses": len(self.courses), "nClasses": len(self.classes), "nDepts": len(self.depts),
                     "nRulesChecked": n_chk, "nRestricted": n_restr,
                     **({"nSpecial": n_special} if n_special else {}),
                     "note": "課程、教師、教室、時間、人數上限、限修條件取自學校公開網頁；已選人數無公開資料，網站上為示範數字。"}

    # ------------------------------------------------------------------ lookups
    def get(self, code):
        code = str(code or "").strip()
        return self.by_code.get(code) or self.by_code.get(code.upper())

    def find_class(self, program, dept, grade, section):
        for c in self.classes:
            if c["dept"]["program"] == program and c["dept"]["label"] == dept and c["grade"] == int(grade or 0) \
                    and (c["section"] or "") == (section or ""):
                return c
        return None

    @staticmethod
    def type_for(co, mine):
        l = next((x for x in co["listings"] if mine and x["cls"] is mine), None)
        req = l["req"] if l else ("通" if co["general"] else (co["primary"]["req"] if co["primary"] else ""))
        return "必修" if req == "必" else "通識" if req == "通" else "選修"

    # ------------------------------------------------------------------ JSON shapes
    @staticmethod
    def class_json(cl, with_items=False):
        d = {"id": cl["id"], "i": cl["i"], "label": cl["label"], "grade": cl["grade"], "section": cl["section"],
             "dept": cl["dept"]["label"], "program": cl["dept"]["program"], "scraped": cl["scraped"]}
        if with_items:
            d["nCourses"] = len(cl["items"])
        return d

    def course_json(self, co, student=None, mine=None, seat_delta=None):
        """單門課 → JSON。欄位名稱與前端 decodeCourse() 相同，所以前端可以直接用。"""
        delta = (seat_delta or {}).get(co["code"], 0)
        enrolled = min(co["cap"], co["enrolledBase"] + delta) if co["cap"] else 0
        d = {k: co[k] for k in ("idx", "code", "no", "cid", "name", "teacher", "credits", "hours", "cap", "unlimited",
                                "term", "group", "note", "ocls", "slots", "restr", "tba", "placeholder", "room",
                                "dept", "program", "grade", "clsLabel", "general")}
        d["enrolled"] = enrolled
        d["enrolledSimulated"] = True          # ← 已選人數是模擬的（學校沒有公開）
        d["remain"] = 999 if not co["cap"] else max(0, co["cap"] - enrolled)
        d["listings"] = [{"classId": l["cls"]["id"], "cls": l["cls"]["label"], "req": l["req"]} for l in co["listings"]]
        d["type"] = self.type_for(co, mine)
        if co["special"]:
            d["special"] = {"kind": co["special"][0], "reason": co["special"][1], "blocking": co["specialBlocking"],
                            "tags": [{"kind": k, "names": n, "blocking": bool(b)} for k, n, b in co["special"][2]]}
        if student is not None:
            d["eligible"] = can_take(co["restr"], student)
        return d

    def courses_bundle(self):
        """= SCU.REAL_COURSES（scu-scraper/export_frontend.py 的輸出格式）"""
        rows = []
        for co in self.courses:
            ss = [[s["day"], s["start"], s["end"], s["room"], s["wk"]] + ([s["teacher"]] if s["teacher"] else [])
                  for s in co["slots"]]
            rows.append([co["code"], co["no"], co["cid"], co["name"], co["teacher"], co["credits"], co["hours"],
                         co["cap"], co["term"], co["group"], co["note"], co["ocls"], ss, co["restr"], co["tbaFlag"], co["special"] or 0])
        return {"meta": self.meta, "periods": [list(p) for p in PERIOD_TIMES],
                "fields": ["key", "no", "cid", "name", "teacher", "credits", "hours", "cap", "term", "group", "note",
                           "offeringClass", "sessions[[day,start,end,room,week,teacher?]]", "restr", "tba",
                           "special[kind, reason, [[kind, names[], blocking]]] or 0"],
                "courses": rows}

    def classes_bundle(self):
        """= SCU.REAL_CLASSES"""
        return {"fields": {"programs": ["code", "label"], "depts": ["programCode", "label", "isGeneral"],
                           "classes": ["deptIndex", "label", "grade", "section", "scraped", "courses[[courseIndex, 必/選]]"]},
                "programs": [[p["code"], p["label"]] for p in self.programs],
                "depts": [[d["programCode"], d["label"], 1 if d["general"] else 0] for d in self.depts],
                "classes": [[c["dept"]["i"], c["label"], c["grade"], c["section"] or None, 1 if c["scraped"] else 0, c["items"]]
                            for c in self.classes]}
