from django.contrib import admin

from .models import LiveStream


@admin.register(LiveStream)
class LiveStreamAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "created_by", "started_at", "ended_at")
    list_filter = ("is_active",)
    readonly_fields = ("stream_key", "started_at")
