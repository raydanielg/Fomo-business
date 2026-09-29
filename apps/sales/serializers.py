from decimal import Decimal
from rest_framework import serializers

from apps.payments.models import Payment
from .models import Sale, SaleItem


class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)

    class Meta:
        model = SaleItem
        fields = [
            "id", "product", "product_name", "product_sku",
            "quantity", "unit_price", "discount", "tax", "total",
        ]


class SalePaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "amount", "method", "reference", "status", "paid_at"]


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    payments = SalePaymentSerializer(many=True, read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True, default="")
    cashier_email = serializers.CharField(source="cashier.email", read_only=True, default="")

    class Meta:
        model = Sale
        fields = [
            "id", "branch", "branch_name", "customer", "customer_name",
            "invoice", "cashier", "cashier_email", "receipt_number",
            "subtotal", "discount", "tax", "total", "amount_paid",
            "balance_due", "payment_status", "status", "notes",
            "items", "payments", "created_at", "updated_at",
        ]
        read_only_fields = fields


class SaleItemInputSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    unit_price = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, min_value=0
    )
    discount = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=0, min_value=0
    )


class PaymentInputSerializer(serializers.Serializer):
    method = serializers.ChoiceField(
        choices=["CASH", "MOBILE_MONEY", "BANK", "CARD", "OTHER"]
    )
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    reference = serializers.CharField(required=False, allow_blank=True, default="")


class SaleCreateSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField()
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    items = SaleItemInputSerializer(many=True)
    discount = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=0, min_value=0
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    payment = PaymentInputSerializer(required=False, allow_null=True)
    draft = serializers.BooleanField(default=False)


class SaleActionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
