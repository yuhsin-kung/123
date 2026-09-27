from django.contrib import admin

from .models import Announcement, CrawlLog, Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("start_date", "end_date", "category", "title", "source_name", "semester", "audience", "is_active")
    list_filter = ("category", "source_name", "semester", "audience", "is_active")
    search_fields = ("title", "raw_text")
    date_hierarchy = "start_date"


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("date", "unit", "title", "category", "tag", "source_name")
    list_filter = ("source_name", "category", "tag")
    search_fields = ("title", "unit")
    date_hierarchy = "date"


@admin.register(CrawlLog)
class CrawlLogAdmin(admin.ModelAdmin):
    list_display = ("started_at", "source_name", "status", "n_items", "message")
    list_filter = ("status", "source_name")
