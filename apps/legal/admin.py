from django.contrib import admin

from .models import LegalDocument, LegalAcceptance


@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "doc_type", "version", "effective_date",
                    "is_current", "requires_acceptance")
    list_filter = ("doc_type", "is_current", "requires_acceptance")
    search_fields = ("title", "version")


@admin.register(LegalAcceptance)
class LegalAcceptanceAdmin(admin.ModelAdmin):
    list_display = ("user", "document", "accepted_at", "ip_address")
    list_filter = ("document__doc_type", "accepted_at")
    readonly_fields = ("accepted_at",)
