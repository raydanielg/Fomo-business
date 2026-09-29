from decimal import Decimal
from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True, default="")
    received_by_email = serializers.CharField(source="received_by.email", read_only=True, default="")

    class Meta:
        model = Payment
        fields = [
            "id", "branch", "sale", "invoice", "customer", "customer_name",
            "amount", "method", "reference", "status", "paid_at",
            "received_by", "received_by_email", "metadata", "created_at",
        ]
        read_only_fields = fields


class RecordPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    method = serializers.ChoiceField(choices=Payment.Method.choices)
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    sale_id = serializers.UUIDField(required=False, allow_null=True)
    invoice_id = serializers.UUIDField(required=False, allow_null=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    branch_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        if not any([attrs.get("sale_id"), attrs.get("invoice_id"), attrs.get("customer_id")]):
            raise serializers.ValidationError(
                "A payment must reference a sale, invoice, or customer."
            )
        return attrs


class InvoicePaymentSerializer(serializers.Serializer):
    """Payment against an invoice identified by URL — no target fields needed."""

    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0.01")
    )
    method = serializers.ChoiceField(choices=Payment.Method.choices)
    reference = serializers.CharField(required=False, allow_blank=True, default="")
