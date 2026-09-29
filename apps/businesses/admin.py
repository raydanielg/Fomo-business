from django.contrib import admin

from .models import Business


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "business_type", "status", "country", "currency", "created_at"]
    list_filter = ["status", "business_type", "country"]
    search_fields = ["name", "slug", "email", "phone", "registration_number", "tax_number"]
    readonly_fields = ["id", "created_at", "updated_at"]
    prepopulated_fields = {"slug": ("name",)}
