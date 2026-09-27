from django.urls import path

from . import views

urlpatterns = [
    path("selection/window", views.window_api),
    path("me/timetable", views.my_timetable_api),
    path("cart", views.cart_api),
    path("cart/submit", views.submit_api),
]
