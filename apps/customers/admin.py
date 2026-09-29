from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["name", "business", "phone", "current_balance", "is_active"]
    list_filter = ["is_active", "business"]
    search_fields = ["name", "phone", "email"]
    readonly_fields = ["id", "created_at", "updated_at"]
