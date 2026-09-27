from django.contrib import admin

from .models import StudentProfile


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("student_id", "name", "program", "dept", "grade", "cls", "college", "user", "is_demo")
    search_fields = ("student_id", "name", "dept", "user__username")
