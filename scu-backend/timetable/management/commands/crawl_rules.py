# 複製自 scu-scraper/django_draft/timetable/management/commands/（2026-09-26 快照）。會連網：全校約 520 個請求、≥1.2 秒/請求。
"""python manage.py crawl_rules --semester 115-1 [--dept 資料科學系 ...] [--all] [--limit N]

Fetch the public 選課限制資料查詢 page (SelectCar/selrule12.asp?courid=&corder=) for each 科目代碼
already crawled by crawl_timetable, store CourseRule rows and a merged CourseRestriction.
Polite: shares PoliteClient (≥1.2 s between requests, stop on 403/429). Run once per semester after
crawl_timetable (before 初選), optionally again before 加退選.
"""
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from timetable.models import ClassCourse, Course, CourseRestriction, CourseRule
from timetable.scu import class40 as scu


class Command(BaseCommand):
    def add_arguments(self, p):
        p.add_argument("--semester", required=True)
        p.add_argument("--dept", action="append")
        p.add_argument("--all", action="store_true")
        p.add_argument("--limit", type=int, default=0)

    def handle(self, semester, dept, all, limit, **_):
        qs = ClassCourse.objects.filter(course__semester=semester).select_related("course", "school_class__department")
        if not all:
            qs = qs.filter(school_class__department__label__in=dept or [])
        notes = {}
        for cc in qs:
            c = cc.course
            notes.setdefault(c.course_code, (c.note, c.group_name, cc.school_class.department.label))
        done = set(CourseRestriction.objects.filter(semester=semester, rules_checked=True).values_list("course_code", flat=True))
        codes = sorted(c for c in notes if c not in done and len(c) == 8)[: limit or None]
        raw_dir = Path(getattr(settings, "SCU_RAW_DIR", "raw")) / semester / ("rules_" + timezone.now().strftime("%Y%m%dT%H%M%S"))
        res = scu.crawl_rules(semester, codes, raw_dir)
        now = timezone.now()
        with transaction.atomic():
            for code, rows in res.items():
                CourseRule.objects.filter(semester=semester, course_code=code).delete()
                CourseRule.objects.bulk_create([CourseRule(semester=semester, course_code=code, rule_code=r["rule_code"],
                    description=r["description"], phase=r["phase"], allow=None if r["allow"] is None else bool(r["allow"]),
                    dimension=r["dimension"], values=r["values"], exceptions=r["exceptions"], raw=r["raw"], scraped_at=now)
                    for r in rows])
                rr = scu.restriction_from_rules(rows) if rows else {}
                nn = scu.restriction_from_note(*notes[code])
                merged = {k: rr.get(k) or nn.get(k) for k in set(rr) | set(nn)}
                src = "+".join(n for n, part in (("selrule", rr), ("note", nn)) if part and any(part.values())) or "none"
                CourseRestriction.objects.update_or_create(semester=semester, course_code=code, defaults=dict(
                    min_grade=merged.get("min_grade"), max_grade=merged.get("max_grade"), grades=merged.get("grades"),
                    dept_only=merged.get("dept_only"), program_only=merged.get("program_only"),
                    class_only=merged.get("class_only"), dept_exclude=merged.get("dept_exclude"), exceptions=merged.get("exceptions"),
                    other_text=merged.get("other_text") or "", source=src, rules_checked=True, scraped_at=now))
        self.stdout.write(f"rules stored for {len(res)} course codes")
