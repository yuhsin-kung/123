"""config/urls.py — 網址總表：URL → view

  /admin/            Django 內建管理介面
  /accounts/login/   Django 內建登入頁（模板在 accounts/templates/registration/login.html）
  /api/...           JSON API（各 app 的 urls.py）
  /、/js/、/css/     前端網站（portal app）
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path

from portal import views as portal_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("api/", include("accounts.urls")),
    path("api/", include("timetable.urls")),
    path("api/", include("events.urls")),
    path("api/", include("enrollment.urls")),
    path("", portal_views.index, name="home"),
    re_path(r"^(?P<path>(?:js|css|kb|img|shots)/.+)$", portal_views.asset),
]

admin.site.site_header = "東吳學生新入口｜資料管理（示範）"
admin.site.site_title = "SCU Portal Admin"
admin.site.index_title = "資料表"
