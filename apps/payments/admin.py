from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["amount", "method", "business", "status", "paid_at"]
    list_filter = ["method", "status", "business"]
    search_fields = ["reference", "customer__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
