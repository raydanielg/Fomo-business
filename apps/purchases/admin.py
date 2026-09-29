from django.contrib import admin

from .models import Purchase, PurchaseItem


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ["reference", "business", "supplier", "total", "status", "created_at"]
    list_filter = ["status", "business"]
    search_fields = ["reference", "supplier__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [PurchaseItemInline]
