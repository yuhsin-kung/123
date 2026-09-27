from django.urls import path

from . import views

urlpatterns = [
    path("periods", views.periods_api),
    path("programs", views.programs_api),
    path("departments", views.departments_api),
    path("classes", views.classes_api),
    path("classes/<int:class_index>/timetable", views.class_timetable_api),
    path("class-timetable", views.class_timetable_lookup_api),
    path("courses", views.courses_api),
    path("courses/<str:code>", views.course_detail_api),
    path("bundle/courses", views.courses_bundle_api),
    path("bundle/classes", views.classes_bundle_api),
]
