"""enrollment/clock.py — 系統的「現在」是幾點？（示範用、可設定）

優先順序：
  1. admin 的「示範時鐘」DemoClock（啟用時）
  2. settings.SCU_DEMO_NOW（環境變數可改；預設 "2026-09-30T10:30" 台北時間）
  3. SCU_DEMO_NOW="real" → 真正的現在時間
注意：送出選課只看伺服器這裡的時間，不看瀏覽器傳來的時間 → 使用者沒辦法自己把時間改回選課期間。
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

TZ = ZoneInfo("Asia/Taipei")


def parse_local(s):
    """'2026-09-30T10:30' / '2026-09-30 10:30' / '2026-09-30' → 台北時間的 aware datetime"""
    s = str(s).strip().replace(" ", "T")
    d = datetime.fromisoformat(s if "T" in s else s + "T00:00")
    return d if d.tzinfo else d.replace(tzinfo=TZ)


def demo_now():
    from .models import DemoClock
    clock = DemoClock.objects.filter(enabled=True).order_by("-id").first()
    if clock:
        return timezone.localtime(clock.now, TZ)
    v = getattr(settings, "SCU_DEMO_NOW", "real")
    if not v or str(v).lower() == "real":
        return timezone.localtime(timezone.now(), TZ)
    return parse_local(v)


def clock_source():
    from .models import DemoClock
    if DemoClock.objects.filter(enabled=True).exists():
        return "admin 示範時鐘"
    v = getattr(settings, "SCU_DEMO_NOW", "real")
    return "真實時間" if not v or str(v).lower() == "real" else "settings.SCU_DEMO_NOW"
