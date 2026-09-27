"""timetable/views.py — 課程／班級相關的 JSON API

一個 request 的旅程（寫報告可以用這段當例子）：
  瀏覽器 GET /api/courses?dept=資料科學系&grade=3
   → config/urls.py 把 /api/ 交給 timetable/urls.py
   → timetable/urls.py 對應到 courses_api(request)
   → courses_api 從 request.GET 讀篩選條件，向 catalog（快取的 Model 資料）篩選
   → course_json() 把每門課轉成 dict → api_ok() 轉成 JSON 回傳
"""
from django.conf import settings
from django.views.decorators.http import require_GET

from accounts.services import current_user, student_of
from config.api import api_error, api_ok, int_or_none
from enrollment.seats import seat_delta_map
from enrollment.services import planned_codes

from .catalog import get_catalog
from .eligibility import can_take
from .models import PERIOD_ORDER


def _cat(request):
    return get_catalog(request.GET.get("semester") or settings.SCU_SEMESTER)


def _period_index(v):
    """'3' → 3、'E' → 5、'A' → 11；數字 1..14 也接受"""
    v = str(v or "").strip().upper()
    if not v:
        return None
    if v in PERIOD_ORDER and not v.isdigit():
        return PERIOD_ORDER.index(v) + 1
    n = int_or_none(v)
    if n is None:
        return None
    return PERIOD_ORDER.index(str(n)) + 1 if 1 <= n <= 9 else None


@require_GET
def periods_api(request):
    return api_ok(_cat(request).periods)


@require_GET
def programs_api(request):
    cat = _cat(request)
    used = {d["program"] for d in cat.depts if d["classIds"]}
    return api_ok([p for p in cat.programs if p["label"] in used])


@require_GET
def departments_api(request):
    program = request.GET.get("program", "")
    out = [{"id": d["id"], "i": d["i"], "program": d["program"], "programCode": d["programCode"], "label": d["label"],
            "general": d["general"], "nClasses": len(d["classIds"])}
           for d in _cat(request).depts if d["classIds"] and (not program or d["program"] == program)]
    return api_ok(out)


@require_GET
def classes_api(request):
    program, dept = request.GET.get("program", ""), request.GET.get("dept", "")
    grade = int_or_none(request.GET.get("grade"))
    cat = _cat(request)
    out = [cat.class_json(c, with_items=True) for c in cat.classes
           if (not program or c["dept"]["program"] == program) and (not dept or c["dept"]["label"] == dept)
           and (grade is None or c["grade"] == grade)]
    return api_ok(out)


def _class_timetable(request, cl):
    """回傳格式 = 前端 DS.getClassTimetableById(i) 的 {codes, reqs, cls, note}，另附完整課程資料 courses"""
    if not cl:
        return api_error(404, "class_not_found", "查無此班級。", codes=[], reqs={}, cls=None, note="查無此班級。")
    cat = _cat(request)
    user = current_user(request)
    student, mine = student_of(user)
    delta = seat_delta_map()
    codes, reqs, courses = [], {}, []
    for ci, req in cl["items"]:
        co = cat.courses[ci]
        codes.append(co["code"])
        reqs[co["code"]] = req
        courses.append(cat.course_json(co, student, mine, delta))
    return api_ok({"cls": cat.class_json(cl), "codes": codes, "reqs": reqs, "courses": courses,
                   "note": "" if codes else "學校公開課表上這個班級目前沒有課程資料。"})


@require_GET
def class_timetable_api(request, class_index):
    """GET /api/classes/<i>/timetable：i = 班級在清單中的索引（= real-classes.js 的索引，= 前端 getClassTimetableById(i)）。
    用索引而不用資料庫 id，是因為每學期重新匯入後 id 會變，索引跟前端一致。"""
    classes = _cat(request).classes
    return _class_timetable(request, classes[class_index] if 0 <= class_index < len(classes) else None)


@require_GET
def class_timetable_lookup_api(request):
    """GET /api/class-timetable?program=學士班&dept=資料科學系&grade=3&cls=B（= DS.getClassTimetable）"""
    g = request.GET
    return _class_timetable(request, _cat(request).find_class(g.get("program", ""), g.get("dept", ""),
                                                             g.get("grade"), g.get("cls", "")))


@require_GET
def courses_api(request):
    """找課。參數（都可省略）：
    program、dept、grade：依「出現在哪些班級課表」篩（同前端 inDeptGrade）
    day=1..7、period=3 或 period=5-9 或 from=&to=（1..14 格）：時段找課
    q：關鍵字（課名／教師／選課編號／科目代碼／系所／班級）   type=必修|選修|通識
    eligible=1：只顯示我可以修的（限修檢查）   avail=1：只看有名額   free=1：只看不跟我的課表衝堂
    limit（預設 60，最多 500）、offset：分頁
    """
    g = request.GET
    cat = _cat(request)
    user = current_user(request)
    student, mine = student_of(user)
    delta = seat_delta_map()
    program, dept, grade = g.get("program", ""), g.get("dept", ""), int_or_none(g.get("grade"))
    day = int_or_none(g.get("day"))
    lo = hi = None
    if g.get("period"):
        parts = g["period"].replace("–", "-").split("-")
        lo, hi = _period_index(parts[0]), _period_index(parts[-1])
    elif g.get("from") or g.get("to"):
        lo, hi = int_or_none(g.get("from")) or 1, int_or_none(g.get("to")) or 14
    if lo and hi and lo > hi:
        lo, hi = hi, lo
    q = (g.get("q") or "").strip().lower()
    ctype = g.get("type", "")
    only_ok, avail, free = g.get("eligible") in ("1", "true"), g.get("avail") in ("1", "true"), g.get("free") in ("1", "true")
    planned = []
    if free and user:
        planned = [cat.get(c) for c in planned_codes(user)]
        planned = [c for c in planned if c]
    from enrollment.checks import overlap   # 衝堂判斷與送出檢查共用同一個函式

    out = []
    for co in cat.courses:
        if co["placeholder"]:
            continue
        if (program or dept or grade) and not any(
                (not program or l["cls"]["dept"]["program"] == program) and (not dept or l["cls"]["dept"]["label"] == dept)
                and (grade is None or l["cls"]["grade"] == grade) for l in co["listings"]):
            continue
        if (day or lo) and not any((not day or s["day"] == day) and (not lo or (s["start"] <= hi and s["end"] >= lo))
                                   for s in co["slots"]):
            continue
        if ctype and cat.type_for(co, mine) != ctype:
            continue
        if avail and co["cap"] and co["enrolledBase"] + delta.get(co["code"], 0) >= co["cap"]:
            continue
        if q and q not in " ".join([co["code"], co["no"], co["cid"], co["name"], co["teacher"], co["dept"],
                                    co["clsLabel"]]).lower():
            continue
        if only_ok and student and not can_take(co["restr"], student)["ok"]:
            continue
        if free and any(o["code"] != co["code"] and overlap(co, o) for o in planned):
            continue
        out.append(co)
    my_dept = student["dept"] if student else ""
    first = lambda c: c["slots"][0]["day"] * 100 + c["slots"][0]["start"] if c["slots"] else 9999
    out.sort(key=lambda c: (-(c["dept"] == my_dept), 0 if cat.type_for(c, mine) == "必修" else 1, first(c), c["no"] or c["code"]))
    limit = max(1, min(int_or_none(g.get("limit")) or 60, 500))
    offset = max(0, int_or_none(g.get("offset")) or 0)
    return api_ok({"count": len(out), "offset": offset, "limit": limit, "semester": cat.semester,
                   "results": [cat.course_json(c, student, mine, delta) for c in out[offset:offset + limit]]})


@require_GET
def course_detail_api(request, code):
    cat = _cat(request)
    co = cat.get(code)
    if not co:
        return api_error(404, "course_not_found", f"查無課程 {code}")
    student, mine = student_of(current_user(request))
    return api_ok(cat.course_json(co, student, mine, seat_delta_map()))


@require_GET
def courses_bundle_api(request):
    """= js/real-courses.js 的 SCU.REAL_COURSES（前端換成 fetch 時直接指定給 S.REAL_COURSES 即可）"""
    return api_ok(_cat(request).courses_bundle())


@require_GET
def classes_bundle_api(request):
    """= js/real-classes.js 的 SCU.REAL_CLASSES"""
    return api_ok(_cat(request).classes_bundle())
