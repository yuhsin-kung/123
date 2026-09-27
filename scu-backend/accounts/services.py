"""accounts/services.py — 「現在是誰在用？」

current_user(request)：
  1. 有登入（session）→ 就是那個使用者
  2. 沒登入，且 settings.SCU_DEMO_AUTOLOGIN=True → 當作示範帳號 demo（黑客松展示方便）
  3. 否則 None（API 回 401）
student_of(user) → 給限修檢查用的 dict（program/dept/grade/cls/college/classLabel）
"""
from django.conf import settings
from django.contrib.auth import get_user_model

from timetable.catalog import get_catalog


def current_user(request):
    if request.user.is_authenticated:
        return request.user
    if settings.SCU_DEMO_AUTOLOGIN:
        return get_user_model().objects.filter(username=settings.SCU_DEMO_USERNAME).first()
    return None


def my_class(profile):
    """登入學生所在的班級（catalog 裡的 dict；找不到回 None）"""
    if not profile:
        return None
    return get_catalog(settings.SCU_SEMESTER).find_class(profile.program, profile.dept, profile.grade, profile.cls)


def student_of(user):
    profile = getattr(user, "profile", None) if user else None
    if not profile:
        return None, None
    cl = my_class(profile)
    return profile.to_front(cl["label"] if cl else ""), cl
