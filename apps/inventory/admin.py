from django.contrib import admin

from .models import InventoryMovement, StockLevel


@admin.register(StockLevel)
class StockLevelAdmin(admin.ModelAdmin):
    list_display = ["product", "branch", "business", "quantity", "updated_at"]
    list_filter = ["business", "branch"]
    search_fields = ["product__name", "product__sku"]
    readonly_fields = ["id", "updated_at"]


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ["product", "branch", "movement_type", "quantity", "balance_after", "created_at"]
    list_filter = ["movement_type", "business", "branch"]
    search_fields = ["product__name", "reference_id", "note"]
    readonly_fields = ["id", "created_at", "updated_at"]
