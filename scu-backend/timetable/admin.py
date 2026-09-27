"""timetable/admin.py — 把課程資料表註冊到 Django admin（/admin/），可以瀏覽、搜尋、篩選"""
from django.contrib import admin

from .models import (ClassCourse, Course, CourseRestriction, CourseRule, CourseSession, Department, Program,
                     SchoolClass, ScrapeRun)


@admin.register(ScrapeRun)
class ScrapeRunAdmin(admin.ModelAdmin):
    list_display = ("semester", "started_at", "finished_at", "status", "is_full", "n_classes", "n_requests", "note")
    list_filter = ("semester", "status", "is_full")


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("semester", "code", "label", "form_value")
    list_filter = ("semester",)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("semester", "program", "label", "form_value")
    list_filter = ("semester", "program__label")
    search_fields = ("label",)


class ClassCourseInline(admin.TabularInline):
    model = ClassCourse
    extra = 0
    raw_id_fields = ("course",)


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ("semester", "label", "department", "grade", "section", "timetable_scraped_at")
    list_filter = ("semester", "department__program__label", "grade")
    search_fields = ("label", "department__label")
    inlines = [ClassCourseInline]


class CourseSessionInline(admin.TabularInline):
    model = CourseSession
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("selection_no", "course_code", "name", "teacher", "credits", "capacity", "offering_class",
                    "group_name", "note", "semester")
    list_filter = ("semester", "term_type", "group_name")
    search_fields = ("selection_no", "course_code", "name", "teacher", "offering_class")
    inlines = [CourseSessionInline]


@admin.register(ClassCourse)
class ClassCourseAdmin(admin.ModelAdmin):
    list_display = ("school_class", "course", "req_elective")
    list_filter = ("req_elective",)
    search_fields = ("school_class__label", "course__name", "course__selection_no")
    raw_id_fields = ("school_class", "course")


@admin.register(CourseSession)
class CourseSessionAdmin(admin.ModelAdmin):
    list_display = ("course", "weekday", "periods", "start_time", "end_time", "week_type", "room", "teacher")
    list_filter = ("weekday", "week_type")
    search_fields = ("course__name", "course__selection_no", "room")
    raw_id_fields = ("course",)


@admin.register(CourseRule)
class CourseRuleAdmin(admin.ModelAdmin):
    list_display = ("semester", "course_code", "description", "phase", "allow", "dimension", "values", "exceptions")
    list_filter = ("semester", "phase", "dimension", "allow")
    search_fields = ("course_code",)


@admin.register(CourseRestriction)
class CourseRestrictionAdmin(admin.ModelAdmin):
    list_display = ("semester", "course_code", "grades", "min_grade", "dept_only", "program_only", "class_only",
                    "dept_exclude", "source", "rules_checked")
    list_filter = ("semester", "source", "rules_checked")
    search_fields = ("course_code",)
