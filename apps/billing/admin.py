from django.contrib import admin

from .models import (
    CheckoutSession, PaymentEvent, PaymentLink, PaymentProvider,
    ProviderPayment, Payout, ReconciliationRecord, Refund, WebhookEvent,
)


@admin.register(PaymentProvider)
class PaymentProviderAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "environment", "status", "is_primary",
                    "last_success_at", "last_failure_at"]
    readonly_fields = ["last_success_at", "last_failure_at", "last_error"]


@admin.register(ProviderPayment)
class ProviderPaymentAdmin(admin.ModelAdmin):
    list_display = ["reference", "provider", "business", "amount", "currency",
                    "channel", "status", "created_at", "completed_at"]
    list_filter = ["status", "provider", "channel"]
    search_fields = ["reference", "external_reference", "customer_phone",
                     "customer_email", "customer_name"]
    readonly_fields = ["idempotency_key", "metadata"]


@admin.register(CheckoutSession)
class CheckoutSessionAdmin(admin.ModelAdmin):
    list_display = ["session_reference", "business", "amount", "currency",
                    "status", "created_at", "expires_at"]
    list_filter = ["status", "provider"]


@admin.register(PaymentLink)
class PaymentLinkAdmin(admin.ModelAdmin):
    list_display = ["reference", "business", "amount", "status",
                    "payments_count", "total_collected", "created_at"]
    list_filter = ["status"]


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ["reference", "payment", "amount", "status", "created_at"]
    list_filter = ["status"]


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ["reference", "recipient_name", "channel", "amount",
                    "total", "status", "created_at"]
    list_filter = ["status", "channel"]
    search_fields = ["reference", "external_reference", "recipient_phone"]


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ["event_id", "event_type", "provider", "signature_status",
                    "status", "attempts", "processing_ms", "received_at"]
    list_filter = ["status", "signature_status", "event_type"]
    readonly_fields = ["payload"]


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ["event_type", "payment", "amount", "currency", "source",
                    "created_at"]
    list_filter = ["event_type", "source"]


@admin.register(ReconciliationRecord)
class ReconciliationAdmin(admin.ModelAdmin):
    list_display = ["internal_reference", "provider", "internal_amount",
                    "external_amount", "status", "checked_at", "reviewed_at"]
    list_filter = ["status"]
