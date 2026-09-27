"""enrollment/services.py — 選課的商業邏輯（view 只負責收 request／回 JSON，邏輯放這裡比較好測試）"""
import re

from django.conf import settings
from django.db import transaction

from timetable.catalog import get_catalog
from timetable.eligibility import can_take

from .checks import credits_of, overlap, run_checks
from .models import CartItem, Enrollment
from .seats import seat_delta_map


def sem():
    return settings.SCU_SEMESTER


def timetable_codes(user):
    return list(Enrollment.objects.filter(user=user, semester=sem()).values_list("course_key", flat=True))


def cart_of(user):
    add, drop = [], []
    for it in CartItem.objects.filter(user=user, semester=sem()):
        (add if it.action == CartItem.Action.ADD else drop).append(it.course_key)
    return {"add": add, "drop": drop}


def planned_codes(user):
    """送出後的課表 = 目前課表 − 待退選 + 待加選（同前端 S.plannedCodes）"""
    tt, cart = timetable_codes(user), cart_of(user)
    return [c for c in tt if c not in cart["drop"]] + [c for c in cart["add"] if c not in tt]


def evaluate(user, student):
    """算出送出前檢查結果（GET /api/cart 與 POST /api/cart/submit 共用）"""
    cat = get_catalog(sem())
    tt = set(timetable_codes(user))
    cart = cart_of(user)
    planned = [c for c in (cat.get(x) for x in planned_codes(user)) if c]
    adds = [c for c in (cat.get(x) for x in cart["add"]) if c and c["code"] not in tt]
    return run_checks(planned, adds, student, seat_delta_map()), cart, planned


def default_timetable(student, my_class):
    """示範學生的初始課表（同前端 DS.defaultTimetable）：班級必修＋依序挑本班選修湊到約 18 學分"""
    if not my_class:
        return []
    cat = get_catalog(sem())
    items = [(cat.courses[ci], req) for ci, req in my_class["items"]]
    picked = [c for c, req in items if req == "必"]
    credits = credits_of(picked)
    for c, req in items:
        if req == "必":
            continue
        if credits >= 18 or c["placeholder"] or c["tba"] or re.search("遠距", c["note"] or ""):
            continue
        if not can_take(c["restr"], student)["ok"]:
            continue
        if any(overlap(c, o) for o in picked):
            continue
        picked.append(c)
        credits += c["credits"]
    return [c["code"] for c in picked]


@transaction.atomic
def seed_timetable(user, student, my_class, reset=False):
    if reset:
        Enrollment.objects.filter(user=user, semester=sem()).delete()
        CartItem.objects.filter(user=user, semester=sem()).delete()
    if Enrollment.objects.filter(user=user, semester=sem()).exists():
        return timetable_codes(user)
    codes = default_timetable(student, my_class)
    Enrollment.objects.bulk_create([Enrollment(user=user, semester=sem(), course_key=c, source=Enrollment.Source.SEED)
                                    for c in codes])
    return codes


@transaction.atomic
def apply_cart(user, cart):
    Enrollment.objects.filter(user=user, semester=sem(), course_key__in=cart["drop"]).delete()
    existing = set(timetable_codes(user))
    Enrollment.objects.bulk_create([Enrollment(user=user, semester=sem(), course_key=c, source=Enrollment.Source.SUBMIT)
                                    for c in cart["add"] if c not in existing])
    CartItem.objects.filter(user=user, semester=sem()).delete()
