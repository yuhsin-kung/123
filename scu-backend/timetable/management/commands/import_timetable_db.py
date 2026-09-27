"""python manage.py import_timetable_db --semester 115-1 [--db data/scu_timetable.db]

把 scu-scraper 爬好的 SQLite（scu_timetable.db）匯入 Django 資料庫，不用重新爬全校（約 520 個請求）。
流程跟 crawl_timetable 一樣是「整個學期換新」，而且包在 transaction.atomic() 裡：
中途出錯 → 全部復原，資料庫不會只剩一半。

對照表（爬蟲 SQLite → Django model）：
  scrape_runs → ScrapeRun        programs → Program        departments → Department
  classes → SchoolClass           courses → Course          class_courses → ClassCourse
  course_sessions → CourseSession course_rules → CourseRule course_restrictions → CourseRestriction
爬蟲之後若多了新欄位（例如第二專長標記），會放進 Course.extra / CourseRestriction.extra，不會出錯。
"""
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from timetable.catalog import clear_cache
from timetable.models import (ClassCourse, Course, CourseRestriction, CourseRule, CourseSession, Department,
                              Program, SchoolClass, ScrapeRun)

COURSE_COLS = {"id", "semester", "course_code", "selection_no", "name", "offering_class", "group_name", "term_type",
               "credits", "hours", "capacity", "teacher", "note", "plan_url", "teacher_url", "scraped_at",
               "offering_key", "scrape_run_id"}
RESTR_COLS = {"semester", "course_code", "min_grade", "max_grade", "grades", "dept_only", "program_only",
              "class_only", "exceptions", "other_text", "source", "rules_checked", "scraped_at", "dept_exclude"}


def dt(s):
    if not s:
        return None
    d = datetime.fromisoformat(s)
    return d if timezone.is_aware(d) else timezone.make_aware(d)


def jl(s):
    if s is None or s == "":
        return None
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return s


def tm(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%H:%M").time()
    except ValueError:
        return None


class Command(BaseCommand):
    help = "從 scu_timetable.db 匯入一個學期的課程資料（不連網）"

    def add_arguments(self, p):
        p.add_argument("--semester", required=True, help="例如 115-1")
        p.add_argument("--db", default=str(settings.SCU_TIMETABLE_DB))

    def handle(self, semester, db, **_):
        path = Path(db)
        if not path.exists():
            raise CommandError(f"找不到 {path}")
        t0 = time.monotonic()
        con = sqlite3.connect(path)
        con.row_factory = sqlite3.Row
        if not con.execute("SELECT 1 FROM courses WHERE semester=? LIMIT 1", (semester,)).fetchone():
            raise CommandError(f"{path.name} 裡沒有 {semester} 的課程")
        with transaction.atomic():
            counts = self._import(con, semester)
        clear_cache()
        self.stdout.write(self.style.SUCCESS(
            f"{semester} 匯入完成（{time.monotonic() - t0:.1f} 秒）：" + "、".join(f"{k} {v}" for k, v in counts.items())))

    def _import(self, con, sem):
        # 1) 先刪掉這個學期的舊資料（ForeignKey on_delete=CASCADE 會連帶刪掉系所、班級、時段…）
        Course.objects.filter(semester=sem).delete()
        Program.objects.filter(semester=sem).delete()
        CourseRule.objects.filter(semester=sem).delete()
        CourseRestriction.objects.filter(semester=sem).delete()
        ScrapeRun.objects.filter(semester=sem, note__startswith="imported from").delete()  # 上次匯入的紀錄

        runs = {}
        for r in con.execute("SELECT * FROM scrape_runs WHERE semester=? ORDER BY id", (sem,)):
            runs[r["id"]] = ScrapeRun.objects.create(
                semester=sem, started_at=dt(r["started_at"]), finished_at=dt(r["finished_at"]), status=r["status"],
                is_full=(r["note"] == "full crawl"), n_classes=r["n_classes"] or 0, n_requests=r["n_requests"] or 0,
                raw_dir=(r["raw_dir"] or "")[:500], note=f"imported from scu_timetable.db: {r['note'] or ''}")
        latest = runs[max(runs)] if runs else None

        def run_of(row):
            rid = row["scrape_run_id"] if "scrape_run_id" in row.keys() else None
            return runs.get(rid, latest)

        progs = {}
        for r in con.execute("SELECT * FROM programs WHERE semester=?", (sem,)):
            progs[r["id"]] = Program.objects.create(semester=sem, code=r["code"], form_value=r["form_value"],
                                                    label=r["label"], scrape_run=run_of(r), scraped_at=dt(r["scraped_at"]))
        depts = {}
        for r in con.execute("SELECT * FROM departments WHERE semester=? ORDER BY id", (sem,)):
            depts[r["id"]] = Department.objects.create(
                semester=sem, program=progs[r["program_id"]], form_value=r["form_value"], label=r["label"],
                class_key=r["class_key"], scrape_run=latest, scraped_at=dt(r["scraped_at"]))
        rows = list(con.execute("SELECT * FROM classes WHERE semester=? ORDER BY id", (sem,)))
        objs = SchoolClass.objects.bulk_create([SchoolClass(
            semester=sem, department=depts[r["department_id"]], form_value=r["form_value"], label=r["label"],
            abbr=r["abbr"] or "", grade=r["grade"], section=r["section"] or "",
            timetable_scraped_at=dt(r["timetable_scraped_at"]), scrape_run=latest, scraped_at=dt(r["scraped_at"]))
            for r in rows])
        classes = {r["id"]: o for r, o in zip(rows, objs)}

        rows = list(con.execute("SELECT * FROM courses WHERE semester=? ORDER BY id", (sem,)))
        objs = Course.objects.bulk_create([Course(
            semester=sem, course_code=r["course_code"], selection_no=r["selection_no"] or "",
            offering_key=r["offering_key"], name=r["name"], offering_class=r["offering_class"] or "",
            group_name=r["group_name"] or "", term_type=r["term_type"] or "", credits=r["credits"], hours=r["hours"],
            capacity=r["capacity"], teacher=r["teacher"] or "", note=r["note"] or "",
            plan_url=(r["plan_url"] or "")[:500], teacher_url=(r["teacher_url"] or "")[:500],
            scrape_run=run_of(r), scraped_at=dt(r["scraped_at"]),
            extra={k: jl(r[k]) if isinstance(r[k], str) and r[k][:1] in "[{" else r[k]
                   for k in r.keys() if k not in COURSE_COLS and r[k] not in (None, "")})
            for r in rows], batch_size=500)
        courses = {r["id"]: o for r, o in zip(rows, objs)}
        if any(o.pk is None for o in objs):
            raise CommandError("bulk_create 沒有回傳主鍵（SQLite 版本太舊？需要 3.35 以上）")

        links = [ClassCourse(school_class=classes[x["class_id"]], course=courses[x["course_id"]],
                             req_elective=x["req_elective"] or "")
                 for x in con.execute("SELECT * FROM class_courses")
                 if x["class_id"] in classes and x["course_id"] in courses]
        ClassCourse.objects.bulk_create(links, batch_size=1000)

        sess = [CourseSession(course=courses[s["course_id"]], weekday=s["weekday"], periods=s["periods"] or "",
                              start_time=tm(s["start_time"]), end_time=tm(s["end_time"]),
                              week_type=s["week_type"] or "", room=s["room"] or "", teacher=s["teacher"] or "")
                for s in con.execute("SELECT * FROM course_sessions ORDER BY id") if s["course_id"] in courses]
        CourseSession.objects.bulk_create(sess, batch_size=1000)

        n_rules = n_restr = 0
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "course_rules" in tables:
            rules = [CourseRule(semester=sem, course_code=r["course_code"], rule_code=r["rule_code"] or "",
                                description=r["description"] or "", phase=r["phase"] or "",
                                allow=None if r["allow"] is None else bool(r["allow"]), dimension=r["dimension"] or "",
                                values=jl(r["rule_values"]) or [], exceptions=jl(r["exceptions"]) or [],
                                raw=r["raw"] or "", scraped_at=dt(r["scraped_at"]))
                     for r in con.execute("SELECT * FROM course_rules WHERE semester=?", (sem,))]
            CourseRule.objects.bulk_create(rules, batch_size=1000)
            n_rules = len(rules)
        if "course_restrictions" in tables:
            restr = []
            for r in con.execute("SELECT * FROM course_restrictions WHERE semester=?", (sem,)):
                k = r.keys()
                restr.append(CourseRestriction(
                    semester=sem, course_code=r["course_code"], min_grade=r["min_grade"], max_grade=r["max_grade"],
                    grades=jl(r["grades"]), dept_only=jl(r["dept_only"]), program_only=jl(r["program_only"]),
                    class_only=jl(r["class_only"]), dept_exclude=jl(r["dept_exclude"]) if "dept_exclude" in k else None,
                    exceptions=jl(r["exceptions"]), other_text=r["other_text"] or "", source=r["source"] or "none",
                    rules_checked=bool(r["rules_checked"]), scraped_at=dt(r["scraped_at"]),
                    extra={c: jl(r[c]) if isinstance(r[c], str) else r[c] for c in k
                           if c not in RESTR_COLS and r[c] not in (None, "")}))
            CourseRestriction.objects.bulk_create(restr, batch_size=1000)
            n_restr = len(restr)
        return {"學制": len(progs), "系所": len(depts), "班級": len(classes), "課程": len(courses),
                "班級課表列": len(links), "上課時段": len(sess), "限修原始列": n_rules, "限修條件": n_restr}
