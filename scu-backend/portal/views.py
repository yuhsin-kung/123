"""portal/views.py — 提供前端網站（SCU_FRONTEND_DIR 裡的 index.html、js/、css/）

前端是純 HTML/JS，index.html 用相對路徑載入 js/xxx.js、css/style.css，
所以把網站放在網址根目錄 "/"，並讓 /js/、/css/ 等路徑直接回傳檔案。
開發時用 django.views.static.serve 最簡單；正式上線應改用 WhiteNoise 或 nginx。
"""
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.views.static import serve


def index(request):
    f = Path(settings.SCU_FRONTEND_DIR) / "index.html"
    if not f.exists():
        return HttpResponse("<h1>前端尚未放入</h1><p>請執行 python manage.py sync_frontend --src ..\\scu-portal-demo</p>")
    return FileResponse(open(f, "rb"), content_type="text/html; charset=utf-8")


def asset(request, path):
    root = Path(settings.SCU_FRONTEND_DIR)
    if not root.exists():
        raise Http404
    return serve(request, path, document_root=str(root))
