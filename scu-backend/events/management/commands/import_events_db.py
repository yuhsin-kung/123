"""python manage.py import_events_db [--db data/scu_events.db]

把 scu-events 爬蟲產生的 SQLite（events / announcements / crawl_log 三張表）匯入 Django 資料庫。
不連網。可以重複執行：以 (source_name, uid) / (source_name, news_id) 為鍵做 upsert。
"""
import sqlite3
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from events.models import Announcement, CrawlLog, Event


def _dt(s):
    if not s:
        return timezone.now()
    d = datetime.fromisoformat(s)
    return d if timezone.is_aware(d) else timezone.make_aware(d)


def _d(s):
    return date.fromisoformat(s) if s else None


class Command(BaseCommand):
    help = "從 scu_events.db 匯入行事曆事件與校園公告（不連網）"

    def add_arguments(self, p):
        p.add_argument("--db", default=str(settings.SCU_EVENTS_DB))

    @transaction.atomic
    def handle(self, db, **_):
        path = Path(db)
        if not path.exists():
            raise CommandError(f"找不到 {path}")
        con = sqlite3.connect(path)
        con.row_factory = sqlite3.Row
        ev_fields = ["title", "category", "start_date", "end_date", "source_url", "raw_text", "hash", "semester",
                     "audience", "note", "is_active", "fetched_at", "first_seen"]
        n_new = n_upd = 0
        for r in con.execute("SELECT * FROM events"):
            vals = dict(title=r["title"], category=r["category"], start_date=_d(r["start_date"]),
                        end_date=_d(r["end_date"]), source_url=r["source_url"] or "", raw_text=r["raw_text"] or "",
                        hash=r["hash"], semester=r["semester"] or "", audience=r["audience"] or "student",
                        note=r["note"] or "", is_active=bool(r["is_active"]), fetched_at=_dt(r["fetched_at"]),
                        first_seen=_dt(r["first_seen"]))
            _, created = Event.objects.update_or_create(source_name=r["source_name"], uid=r["uid"], defaults=vals)
            n_new += created
            n_upd += not created
        a_new = a_upd = 0
        for r in con.execute("SELECT * FROM announcements"):
            vals = dict(title=r["title"], date=_d(r["date"]), unit=r["unit"] or "", category=r["category"] or "",
                        tag=r["tag"] or "", url=r["url"] or "", hash=r["hash"], fetched_at=_dt(r["fetched_at"]),
                        first_seen=_dt(r["first_seen"]))
            _, created = Announcement.objects.update_or_create(source_name=r["source_name"], news_id=r["news_id"],
                                                               defaults=vals)
            a_new += created
            a_upd += not created
        n_log = 0
        if not CrawlLog.objects.exists():
            for r in con.execute("SELECT * FROM crawl_log"):
                CrawlLog.objects.create(source_name=r["source_name"] or "", started_at=_dt(r["started_at"]),
                                        status=r["status"] or "", n_items=r["n_items"] or 0,
                                        message=r["message"] or "")
                n_log += 1
        self.stdout.write(self.style.SUCCESS(
            f"events: {n_new} 新增 / {n_upd} 更新；announcements: {a_new} 新增 / {a_upd} 更新；crawl_log: {n_log}"))
