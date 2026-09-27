"""python manage.py crawl_events [--only calendar,news] [--year 115] [--news-pages 3]

Crawls SCU public sources and upserts into Event / Announcement.
  calendar  = ICS (primary) + 行事曆 PDF (cross-check) + 學士班選課註冊時間表 PDF
  news      = news.scu.edu.tw 校園公告 + 德育中心 最新消息 (+ dated deadlines found in titles)
Stops immediately (exit code 2) on HTTP 403/429.
"""
import sys
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from events.crawler import scrape_events as S  # noqa: F401  (sets sys.path for scu_common)
C = S.C  # same module object scrape_events uses (keeps C.Blocked identical)
from events.models import Announcement, CrawlLog, Event


class Command(BaseCommand):
    help = "Crawl 東吳大學 行事曆 / 選課時程 / 校園公告 into the database"

    def add_arguments(self, p):
        p.add_argument("--only", default="calendar,news")
        p.add_argument("--year", type=int, default=None, help="ROC academic year (default: current)")
        p.add_argument("--news-pages", type=int, default=3)
        p.add_argument("--news-detail-limit", type=int, default=10)
        p.add_argument("--delay", type=float, default=C.MIN_INTERVAL)

    # ---- helpers ---------------------------------------------------------
    def _current_roc_year(self):
        t = timezone.localdate()
        return (t.year - 1911) if t.month >= 8 else (t.year - 1912)

    @transaction.atomic
    def _upsert_events(self, source, evs, window=None):
        now = timezone.now()
        seen, ins, upd = set(), 0, 0
        for e in evs:
            h = C.sha1(e["title"], e["start_date"], e.get("end_date"), e["category"], e.get("note"),
                       e.get("semester"), e.get("audience"))
            seen.add(e["uid"])
            obj, created = Event.objects.get_or_create(
                source_name=source, uid=e["uid"],
                defaults=dict(title=e["title"], category=e["category"], start_date=e["start_date"],
                              end_date=e.get("end_date"), source_url=e.get("source_url") or "",
                              raw_text=e.get("raw_text") or "", hash=h, semester=e.get("semester") or "",
                              audience=e.get("audience", "student"), note=e.get("note") or "", fetched_at=now))
            if created:
                ins += 1
            elif obj.hash != h or not obj.is_active:
                for k in ("title", "category", "start_date", "end_date", "semester", "audience"):
                    setattr(obj, k, e.get(k))
                obj.source_url, obj.raw_text = e.get("source_url") or "", e.get("raw_text") or ""
                obj.note, obj.hash, obj.is_active, obj.fetched_at = e.get("note") or "", h, True, now
                obj.save()
                upd += 1
            else:
                Event.objects.filter(pk=obj.pk).update(fetched_at=now)
        deact = 0
        if window:
            deact = (Event.objects.filter(source_name=source, is_active=True,
                                          start_date__range=window).exclude(uid__in=seen)
                     .update(is_active=False))
        return f"{len(evs)} parsed, {ins} new, {upd} changed, {deact} deactivated"

    @transaction.atomic
    def _upsert_announcements(self, items):
        now, new = timezone.now(), 0
        for a in items:
            h = C.sha1(a["title"], a.get("date"), a.get("unit"), a.get("category"))
            obj, created = Announcement.objects.update_or_create(
                source_name=a["source_name"], news_id=a["news_id"],
                defaults=dict(title=a["title"], date=a.get("date"), category=a.get("category") or "",
                              tag=a.get("tag") or "", url=a.get("url") or "", hash=h, fetched_at=now))
            if a.get("unit") and obj.unit != a["unit"]:
                obj.unit = a["unit"]
                obj.save(update_fields=["unit"])
            new += created
        return f"{len(items)} seen, {new} new"

    def _run(self, name, fn):
        started = timezone.now()
        try:
            msg = fn()
            CrawlLog.objects.create(source_name=name, started_at=started, status="ok", message=msg)
            self.stdout.write(self.style.SUCCESS(f"[{name}] {msg}"))
        except C.Blocked:
            CrawlLog.objects.create(source_name=name, started_at=started, status="blocked")
            raise
        except Exception as ex:  # keep other sources going
            CrawlLog.objects.create(source_name=name, started_at=started, status="error", message=repr(ex))
            self.stderr.write(f"[{name}] ERROR {ex!r}")

    # ---- main ------------------------------------------------------------
    def handle(self, *a, **o):
        only = set(o["only"].split(","))
        year = o["year"] or self._current_roc_year()
        lo, hi = C.academic_year_window(year)
        sess = C.PoliteSession(min_interval=o["delay"], log=lambda *x: self.stdout.write(" ".join(map(str, x))))
        try:
            if "calendar" in only:
                self._run("scu_calendar_ics", lambda: self._upsert_events(
                    "scu_calendar_ics", S.scrape_ics(sess, year)[0], (lo, hi)))
                self._run("scu_calendar_pdf", lambda: self._upsert_events(
                    "scu_calendar_pdf", S.scrape_calendar_pdf(sess, year), (lo, hi)))
                self._run("scu_course_timetable", lambda: self._upsert_events(
                    "scu_course_timetable", S.scrape_timetable(sess)))
            if "news" in only:
                # scrape_news() only needs a DB handle to know which ids exist -> give it a tiny shim
                class _Known:
                    def execute(self, _sql, params):
                        exists = Announcement.objects.filter(source_name="news", news_id=params[0])
                        return type("R", (), {"fetchone": lambda s: exists.values("unit").first()})()
                self._run("news", lambda: self._upsert_announcements(
                    S.scrape_news(sess, _Known(), o["news_pages"], o["news_detail_limit"])))
                self._run("units", lambda: self._upsert_announcements(S.scrape_unit_lists(sess)))
        except C.Blocked as ex:
            self.stderr.write(self.style.ERROR(f"STOPPED: {ex}"))
            sys.exit(2)
        self.stdout.write(f"done: {sess.n_requests} HTTP requests")
