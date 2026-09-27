from django.urls import path

from . import views

urlpatterns = [
    path("events", views.events_api),
    path("news", views.news_api),
    path("bundle/events", views.events_bundle),
]
