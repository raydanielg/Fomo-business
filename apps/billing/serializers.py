from rest_framework import serializers

from .models import (
    CheckoutSession, PaymentEvent, PaymentLink, PaymentProvider,
    ProviderPayment, Payout, ReconciliationRecord, Refund, WebhookEvent,
)


class PaymentProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentProvider
        fields = [
            "code", "name", "api_version", "environment", "status",
            "is_primary", "last_success_at", "last_failure_at",
            "last_error", "created_at",
        ]
        read_only_fields = fields


class ProviderPaymentSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source="business.name",
                                          read_only=True, default="")
    provider = serializers.CharField(source="provider.code", read_only=True)

    class Meta:
        model = ProviderPayment
        fields = [
            "id", "reference", "external_reference", "business_name",
            "provider", "channel", "channel_detail",
            "customer_name", "customer_phone", "customer_email",
            "amount", "fee", "net_amount", "currency",
            "status", "status_reason",
            "created_at", "completed_at", "updated_at", "metadata",
        ]
        read_only_fields = fields


class PaymentEventSerializer(serializers.ModelSerializer):
    payment_reference = serializers.CharField(source="payment.reference",
                                              read_only=True, default="")
    business_name = serializers.CharField(
        source="payment.business.name", read_only=True, default="")

    class Meta:
        model = PaymentEvent
        fields = [
            "id", "event_type", "payment_reference", "business_name",
            "amount", "currency", "status", "source", "detail",
            "created_at",
        ]
        read_only_fields = fields


class CheckoutSessionSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source="business.name",
                                          read_only=True, default="")
    provider = serializers.CharField(source="provider.code", read_only=True)

    class Meta:
        model = CheckoutSession
        fields = [
            "id", "session_reference", "business_name", "provider",
            "checkout_url", "payment_link_url", "customer_name",
            "amount", "currency", "status",
            "opened_at", "expires_at", "completed_at", "created_at",
        ]
        read_only_fields = fields


class PaymentLinkSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source="business.name",
                                          read_only=True, default="")

    class Meta:
        model = PaymentLink
        fields = [
            "id", "reference", "url", "description", "business_name",
            "amount", "currency", "custom_amount", "status",
            "payments_count", "total_collected",
            "created_at", "expires_at",
        ]
        read_only_fields = fields


class RefundSerializer(serializers.ModelSerializer):
    payment_reference = serializers.CharField(source="payment.reference",
                                              read_only=True)

    class Meta:
        model = Refund
        fields = [
            "id", "payment_reference", "reference", "amount", "currency",
            "reason", "status", "created_at", "completed_at",
        ]
        read_only_fields = fields


class PayoutSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source="business.name",
                                          read_only=True, default="")
    provider = serializers.CharField(source="provider.code", read_only=True)
    masked_phone = serializers.SerializerMethodField()

    class Meta:
        model = Payout
        fields = [
            "id", "reference", "external_reference", "business_name",
            "provider", "recipient_name", "masked_phone", "channel",
            "amount", "fee", "total", "currency", "narration",
            "status", "status_reason", "created_at", "completed_at",
        ]
        read_only_fields = fields

    def get_masked_phone(self, obj):
        p = obj.recipient_phone or ""
        return f"***{p[-4:]}" if len(p) > 4 else "***"


class WebhookEventSerializer(serializers.ModelSerializer):
    provider = serializers.CharField(source="provider.code", read_only=True)

    class Meta:
        model = WebhookEvent
        fields = [
            "id", "event_id", "event_type", "provider",
            "signature_status", "status", "payment_reference",
            "attempts", "processing_ms", "error",
            "received_at", "processed_at", "payload",
        ]
        read_only_fields = fields


class ReconciliationSerializer(serializers.ModelSerializer):
    provider = serializers.CharField(source="provider.code", read_only=True)

    class Meta:
        model = ReconciliationRecord
        fields = [
            "id", "internal_reference", "external_reference", "provider",
            "internal_amount", "external_amount",
            "internal_status", "external_status",
            "status", "notes", "checked_at", "reviewed_at",
        ]
        read_only_fields = fields
