from django.contrib import admin

from .models import Invoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["invoice_number", "business", "customer", "total", "balance_due", "status", "due_date"]
    list_filter = ["status", "business"]
    search_fields = ["invoice_number", "customer__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [InvoiceItemInline]
