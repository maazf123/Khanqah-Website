from django.contrib import admin

from .models import Writing


@admin.register(Writing)
class WritingAdmin(admin.ModelAdmin):
    list_display = ("title", "published_date")
    list_filter = ("tags",)
    search_fields = ("title", "body")
    filter_horizontal = ("tags",)
