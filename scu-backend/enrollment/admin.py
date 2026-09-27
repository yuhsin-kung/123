from django.contrib import admin

from .models import CartItem, DemoClock, Enrollment, Submission


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("user", "semester", "course_key", "source", "created_at")
    list_filter = ("semester", "source")
    search_fields = ("course_key", "user__username")


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("user", "semester", "course_key", "action", "created_at")
    list_filter = ("semester", "action")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "demo_now", "ok", "status_code", "added", "dropped", "reasons")
    list_filter = ("ok", "status_code")


@admin.register(DemoClock)
class DemoClockAdmin(admin.ModelAdmin):
    list_display = ("enabled", "now", "note")
