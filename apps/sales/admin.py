from django.contrib import admin

from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ["product", "quantity", "unit_price", "discount", "tax", "total"]


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ["receipt_number", "business", "branch", "total", "status", "payment_status", "created_at"]
    list_filter = ["status", "payment_status", "business", "branch"]
    search_fields = ["receipt_number", "customer__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [SaleItemInline]
