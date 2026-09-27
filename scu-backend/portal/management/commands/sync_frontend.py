"""python manage.py sync_frontend --src ..\\scu-portal-demo [--dry-run]

把前端網站「複製一份」到 SCU_FRONTEND_DIR（預設 scu-backend/frontend/），讓 http://127.0.0.1:8000/ 可以打開。
只讀來源資料夾，不修改它。會先刪掉 frontend/ 裡舊的 js/、css/、index.html。
只複製網站需要的檔案：index.html、css/、js/（不含截圖 shots/、eval/、tools/）。
"""
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

KEEP = ["index.html", "css", "js", "kb"]


class Command(BaseCommand):
    help = "複製前端網站（唯讀來源）到 frontend/"

    def add_arguments(self, p):
        p.add_argument("--src", required=True)
        p.add_argument("--dry-run", action="store_true")

    def handle(self, src, dry_run, **_):
        src, dst = Path(src).resolve(), Path(settings.SCU_FRONTEND_DIR)
        if not (src / "index.html").exists():
            raise CommandError(f"{src} 裡沒有 index.html")
        for name in KEEP:
            s, d = src / name, dst / name
            if not s.exists():
                continue
            self.stdout.write(f"{'(dry-run) ' if dry_run else ''}{s} → {d}")
            if dry_run:
                continue
            if d.is_dir():
                shutil.rmtree(d)
            elif d.exists():
                d.unlink()
            (shutil.copytree if s.is_dir() else shutil.copy2)(s, d)
        self.stdout.write(self.style.SUCCESS("完成。重新整理 http://127.0.0.1:8000/ 即可"))
