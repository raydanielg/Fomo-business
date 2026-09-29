from django.contrib import admin

from .models import Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "business", "phone", "balance", "is_active"]
    list_filter = ["is_active", "business"]
    search_fields = ["name", "phone", "email"]
    readonly_fields = ["id", "created_at", "updated_at"]
