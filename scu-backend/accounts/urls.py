from django.urls import path

from . import views

urlpatterns = [
    path("profile", views.profile_api),
    path("login", views.login_api),
    path("logout", views.logout_api),
]
