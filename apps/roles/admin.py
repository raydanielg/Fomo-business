from django.contrib import admin

from .models import Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "business", "is_system"]
    list_filter = ["code", "is_system"]
    search_fields = ["code", "name", "business__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
