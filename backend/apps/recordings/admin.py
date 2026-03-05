from django.contrib import admin

from .models import Recording


@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ("title", "speaker", "recording_date", "uploaded_at")
    list_filter = ("tags", "recording_date")
    search_fields = ("title", "speaker", "description")
    filter_horizontal = ("tags",)
    readonly_fields = ("uploaded_at",)
