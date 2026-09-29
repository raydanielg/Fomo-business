from django.contrib import admin

from .models import Branch


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "business", "city", "is_active", "is_default"]
    list_filter = ["is_active", "business"]
    search_fields = ["name", "code", "business__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
