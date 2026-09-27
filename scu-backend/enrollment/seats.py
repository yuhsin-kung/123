"""enrollment/seats.py — 模擬名額（已選人數）

學校沒有公開即時已選人數，所以：
  已選人數（模擬）＝ fake_enrolled(課程代碼, 人數上限)   ← 固定假數字，與前端相同，約 1/9 門額滿
                   ＋ 本系統裡「送出選課」加選這門課的人數
API 輸出的每門課都帶 enrolledSimulated: true，畫面上要標示「已選人數為示範」。
"""
from django.conf import settings
from django.db.models import Count

from .models import Enrollment


def seat_delta_map(semester=None):
    rows = (Enrollment.objects.filter(semester=semester or settings.SCU_SEMESTER, source=Enrollment.Source.SUBMIT)
            .values("course_key").annotate(n=Count("id")))
    return {r["course_key"]: r["n"] for r in rows}


def remain(course, delta):
    if not course["cap"]:
        return 999
    return max(0, course["cap"] - course["enrolledBase"] - delta.get(course["code"], 0))
