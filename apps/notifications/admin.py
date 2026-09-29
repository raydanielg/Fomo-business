from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["type", "title", "user", "business", "read_at", "created_at"]
    list_filter = ["type", "read_at"]
    search_fields = ["title", "message", "user__email"]
    readonly_fields = ["id", "created_at"]
