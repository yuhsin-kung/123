# 複製自 scu-scraper/django_draft/timetable/management/commands/（2026-09-26 快照）。會連網：全校約 520 個請求、≥1.2 秒/請求。
"""python manage.py crawl_timetable --semester 115-1 [--dept 資料科學系 --program 學士班] [--limit N] [--dry-run]

Once-per-semester full crawl. Network phase first (polite, ~1.2 s/request, archive raw HTML),
then a single transaction.atomic() that deletes the semester's rows and inserts fresh ones.
If anything fails mid-crawl nothing in the DB changes (ScrapeRun is marked failed).
"""
import datetime as dt
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from timetable.models import (ClassCourse, Course, CourseSession, Department, Program,
                              SchoolClass, ScrapeRun)
from timetable.scu import class40 as scu   # = scrape_class40.py


class Command(BaseCommand):
    help = "Crawl the SCU public class timetable (class40.asp) for one semester."

    def add_arguments(self, p):
        p.add_argument("--semester", required=True, help="e.g. 115-1")
        p.add_argument("--program"); p.add_argument("--dept")
        p.add_argument("--limit", type=int, default=0)
        p.add_argument("--dry-run", action="store_true", help="fetch+parse, don't write DB")

    def handle(self, semester, program, dept, limit, dry_run, **_):
        try:
            year, sm = scu.parse_semester(semester)
        except ValueError as e:
            raise CommandError(e)
        full = not (program or dept or limit)
        started = timezone.now()
        raw_dir = Path(getattr(settings, "SCU_RAW_DIR", "raw")) / semester / started.strftime("%Y%m%dT%H%M%S")
        run = ScrapeRun.objects.create(semester=semester, started_at=started, is_full=full, raw_dir=str(raw_dir))
        client = scu.PoliteClient(archive_dir=raw_dir)
        try:
            options = scu.parse_options(client.get_form_page())
            if (options.default_year, options.default_semester) != (year, sm):
                self.stderr.write(f"note: form default is {options.default_year}-{options.default_semester}; "
                                  "class list comes from the live form (current semester).")
            targets = scu.select_classes(options, program, dept)[: limit or None]
            self.stdout.write(f"{len(targets)} classes, ~{len(targets) * scu.MIN_INTERVAL / 60:.1f} min")
            timetables = {}
            for i, c in enumerate(targets, 1):
                html = client.post_timetable(scu.codes_for_class(options, c, year, sm),
                                             archive_name=f"class42_{scu.safe_name(c.value)}.html")
                timetables[c.value] = scu.parse_timetable(html)
                self.stdout.write(f"  [{i}/{len(targets)}] {c.label}: {len(timetables[c.value]['courses'])}")
            if dry_run:
                run.status, run.note = ScrapeRun.Status.OK, "dry-run"
            else:
                self._store(run, semester, options, timetables, full)
                run.status = ScrapeRun.Status.OK
        except Exception as e:
            run.status, run.note = ScrapeRun.Status.FAILED, repr(e)
            raise
        finally:
            run.finished_at, run.n_requests = timezone.now(), client.n_requests
            run.n_classes = len(locals().get("timetables", {}))
            run.save()

    @transaction.atomic
    def _store(self, run, semester, options, timetables, full):
        now = timezone.now()
        common = dict(semester=semester, scrape_run=run, scraped_at=now)
        if full:  # replace whole semester (cascades to departments/classes/links/sessions)
            Course.objects.filter(semester=semester).delete()
            Program.objects.filter(semester=semester).delete()
        progs, depts, classes = {}, {}, {}
        for p in options.programs:
            progs[p.code], _ = Program.objects.update_or_create(
                semester=semester, code=p.code, defaults=dict(common, form_value=p.value, label=p.label))
        for d in options.departments:
            depts[(d.program_code, d.value)], _ = Department.objects.update_or_create(
                semester=semester, program=progs[d.program_code], form_value=d.value,
                defaults=dict(common, label=d.label, class_key=d.class_key))
        for c in options.classes:
            obj, _ = SchoolClass.objects.update_or_create(
                semester=semester, department=depts[(c.program_code, c.dept_value)], form_value=c.value,
                defaults=dict(common, label=c.label, abbr=c.abbr, grade=c.grade, section=c.section or ""))
            classes.setdefault(c.value, []).append(obj)
        for class_value, tt in timetables.items():
            for sc in classes.get(class_value, []):
                ClassCourse.objects.filter(school_class=sc).delete()
                sc.timetable_scraped_at = now; sc.save(update_fields=["timetable_scraped_at"])
                for c in tt["courses"]:
                    okey = c["selection_no"] or f'{c["course_code"]}@{c["offering_class"]}'
                    course, created = Course.objects.get_or_create(
                        semester=semester, course_code=c["course_code"], offering_key=okey,
                        defaults=dict(common, selection_no=c["selection_no"], name=c["course_name"],
                                      offering_class=c["offering_class"], group_name=c["group_name"],
                                      term_type=c["term_type"], credits=c["credits"], hours=c["hours"],
                                      capacity=c["capacity"], teacher=c["teacher"], note=c["note"],
                                      plan_url=c["plan_url"] or "", teacher_url=c["teacher_url"] or ""))
                    ClassCourse.objects.update_or_create(school_class=sc, course=course,
                                                         defaults={"req_elective": c["req_elective"]})
                    if created:
                        for s in c["sessions"]:
                            CourseSession.objects.get_or_create(
                                course=course, weekday=s["weekday"], periods=s["periods"],
                                room=s["room"], week_type=s["week_type"],
                                defaults=dict(teacher=s["teacher"],
                                              start_time=s["start_time"] and dt.time.fromisoformat(s["start_time"]),
                                              end_time=s["end_time"] and dt.time.fromisoformat(s["end_time"])))
