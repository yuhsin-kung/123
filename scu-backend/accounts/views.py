"""accounts/views.py — /api/profile、/api/login、/api/logout

學到的概念：
  * @require_GET / @require_POST：限制 HTTP 方法
  * @ensure_csrf_cookie：讓瀏覽器拿到 csrftoken cookie，之後 fetch POST 要在 header 帶 X-CSRFToken
  * authenticate() / login() / logout()：Django 內建的帳號驗證與 session
"""
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from config.api import api_error, api_ok, read_json

from .services import current_user, student_of


@require_GET
@ensure_csrf_cookie
def profile_api(request):
    user = current_user(request)
    if not user:
        return api_error(401, "not_logged_in", "請先登入")
    student, _ = student_of(user)
    if not student:
        return api_error(404, "no_profile", "這個帳號沒有學生資料（請用 admin 新增 StudentProfile）")
    student["authenticated"] = request.user.is_authenticated
    return api_ok(student)


@require_POST
def login_api(request):
    data = read_json(request)
    user = authenticate(request, username=data.get("username", ""), password=data.get("password", ""))
    if not user:
        return api_error(401, "bad_credentials", "帳號或密碼錯誤")
    login(request, user)
    student, _ = student_of(user)
    return api_ok({"ok": True, "profile": student})


@require_POST
def logout_api(request):
    logout(request)
    return api_ok({"ok": True})
