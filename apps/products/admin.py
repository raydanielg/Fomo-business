from django.contrib import admin

from .models import Category, Product, Unit


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "business", "is_active"]
    list_filter = ["is_active", "business"]
    search_fields = ["name", "business__name"]


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ["name", "abbreviation", "business"]
    search_fields = ["name", "abbreviation"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "sku", "business", "category", "selling_price", "is_active"]
    list_filter = ["is_active", "business", "category"]
    search_fields = ["name", "sku", "barcode", "business__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
