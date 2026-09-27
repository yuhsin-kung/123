"""enrollment/views.py — 選課 API（伺服器端檢查＋選課時段鎖定）

  GET    /api/selection/window         現在能不能選課（?at=2026-09-17T21:00 只能「預覽」，不影響送出）
  GET    /api/me/timetable             我的課表
  GET    /api/cart                     選課車＋送出前檢查結果
  POST   /api/cart  {"code","action"}  加入選課車（action=add 加選／drop 退選）← 不在選課時段 → 403
  DELETE /api/cart  {"code"} 或 ?code= 從選課車移除（沒給 code＝清空）；只是改草稿，任何時候都可以
  POST   /api/cart/submit              送出 ← 不在時段 → 403；檢查不通過（衝堂／學分／額滿／限修）→ 409

HTTP 狀態碼的意思：403 Forbidden「現在不允許這個動作」；409 Conflict「跟你的課表／規則衝突」。
回應裡的 reason / messages 都是中文，前端可以直接顯示。
"""
import json

from django.conf import settings
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.services import current_user, student_of
from config.api import api_error, api_ok, read_json
from timetable.catalog import get_catalog

from .clock import clock_source, demo_now, parse_local
from .models import CartItem, Submission
from .seats import seat_delta_map
from .services import apply_cart, cart_of, evaluate, timetable_codes
from .windows import SCOPE_TEXT, course_in_scope, window_status


def _who(request):
    user = current_user(request)
    if not user:
        return None, None, api_error(401, "not_logged_in", "請先登入")
    student, mine = student_of(user)
    if not student:
        return None, None, api_error(404, "no_profile", "這個帳號沒有學生資料")
    return user, student, None


def _public(ws):
    return {k: v for k, v in ws.items() if not k.startswith("_")}


@require_GET
def window_api(request):
    user, student, err = _who(request)
    if err:
        return err
    at = request.GET.get("at")
    try:
        now = parse_local(at) if at else demo_now()
    except ValueError:
        return api_error(400, "bad_time", "at 參數格式應為 2026-09-17T21:00")
    ws = _public(window_status(student, now))
    ws["clock"] = "預覽（?at=）" if at else clock_source()
    return api_ok(ws)


@require_GET
def my_timetable_api(request):
    user, student, err = _who(request)
    if err:
        return err
    cat = get_catalog(settings.SCU_SEMESTER)
    _, mine = student_of(user)
    delta = seat_delta_map()
    courses = [cat.course_json(c, student, mine, delta) for c in (cat.get(x) for x in timetable_codes(user)) if c]
    return api_ok({"codes": [c["code"] for c in courses],
                   "credits": sum(0 if c["placeholder"] else c["credits"] for c in courses), "courses": courses})


def _cart_payload(user, student, now=None):
    checks, cart, planned = evaluate(user, student)
    ws = window_status(student, now or demo_now())
    return {"add": cart["add"], "drop": cart["drop"], "timetable": timetable_codes(user), "checks": checks,
            "window": {k: ws[k] for k in ("now", "open", "canAdd", "canDrop", "courseScopes", "reason")}}


def _window_block(ws, action, course=None):
    """選課時段檢查：不允許就回傳 403 Response，允許回 None"""
    if action == "add" and not ws["canAdd"]:
        why = ws["reason"] if not ws["canDrop"] else ws["reason"] + "（加選已關閉）"
        return api_error(403, "selection_closed", why, window=_public(ws))
    if action == "drop" and not ws["canDrop"]:
        return api_error(403, "selection_closed", ws["reason"], window=_public(ws))
    if action == "add" and course is not None and not course_in_scope(course, ws["courseScopes"]):
        scope = "、".join(SCOPE_TEXT[s] for s in ws["courseScopes"])
        cur = ws["_select"][0].title if ws["_select"] else ""
        return api_error(403, "course_not_open_in_phase",
                         f"現在是「{cur}」，只開放{scope}；「{course['name']}」({course['no']}) 不在這個階段的開放範圍，"
                         f"請等之後的全校加退選時段。", window=_public(ws))
    return None


@require_http_methods(["GET", "POST", "DELETE"])
def cart_api(request):
    user, student, err = _who(request)
    if err:
        return err
    if request.method == "GET":
        return api_ok(_cart_payload(user, student))

    data = read_json(request)
    code = (data.get("code") or request.GET.get("code") or "").strip()
    sem = settings.SCU_SEMESTER

    if request.method == "DELETE":
        qs = CartItem.objects.filter(user=user, semester=sem)
        if code:
            qs = qs.filter(course_key=code)
        qs.delete()
        return api_ok(_cart_payload(user, student))

    # ---- POST：加入選課車 ----
    action = data.get("action") or "add"
    if action not in ("add", "drop"):
        return api_error(400, "bad_action", "action 只能是 add（加選）或 drop（退選）")
    cat = get_catalog(sem)
    course = cat.get(code)
    if not course:
        return api_error(404, "course_not_found", f"查無課程 {code}")
    ws = window_status(student, demo_now())
    blocked = _window_block(ws, action, course)          # ① 選課時段鎖定（伺服器端）
    if blocked:
        return blocked
    tt = timetable_codes(user)
    if action == "add":
        if course["placeholder"]:
            return api_error(400, "placeholder", f"「{course['name']}」是班級課表上的時段保留列，沒有選課編號，不能選")
        if course["code"] in tt:
            return api_error(409, "already_enrolled", f"「{course['name']}」已經在你的課表上")
    elif course["code"] not in tt:
        return api_error(409, "not_enrolled", f"「{course['name']}」不在你的課表上，不能退選")
    CartItem.objects.update_or_create(user=user, semester=sem, course_key=course["code"],
                                      defaults={"action": action})
    payload = _cart_payload(user, student)
    payload["ok"] = True
    payload["message"] = f"已把「{course['name']}」加入選課車（{'加選' if action == 'add' else '退選'}），送出時會再檢查"
    return api_ok(payload)


@require_POST
def submit_api(request):
    user, student, err = _who(request)
    if err:
        return err
    now = demo_now()
    ws = window_status(student, now)
    cat = get_catalog(settings.SCU_SEMESTER)
    cart = cart_of(user)

    def log(ok, status, reasons):
        Submission.objects.create(user=user, semester=settings.SCU_SEMESTER, demo_now=now, ok=ok, status_code=status,
                                  added=cart["add"], dropped=cart["drop"], reasons=reasons)

    # ① 選課時段鎖定：送出當下再檢查一次（選課車可能是時段內加的，但現在已經關閉）
    for action, codes in (("add", cart["add"]), ("drop", cart["drop"])):
        for code in codes:
            resp = _window_block(ws, action, cat.get(code))
            if resp:
                log(False, 403, [json.loads(resp.content)["reason"]])
                return resp
    if not cart["add"] and not cart["drop"]:
        return api_error(400, "empty_cart", "選課車是空的，沒有要送出的異動")
    # ② 衝堂／學分／額滿（模擬）／限修
    checks, _, _ = evaluate(user, student)
    if not checks["ok"]:
        log(False, 409, checks["messages"])
        return api_error(409, "checks_failed", "送出前檢查沒有通過：" + "；".join(checks["messages"]),
                         checks=checks)
    apply_cart(user, cart)
    log(True, 200, [])
    return api_ok({"ok": True, "message": f"選課已送出：加選 {len(cart['add'])} 門、退選 {len(cart['drop'])} 門",
                   "added": cart["add"], "dropped": cart["drop"], "timetable": timetable_codes(user),
                   "credits": checks["credits"]})
