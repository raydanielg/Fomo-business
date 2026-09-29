from decimal import Decimal
from rest_framework import serializers

from .models import Invoice, InvoiceItem


class InvoiceItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True, default="")

    class Meta:
        model = InvoiceItem
        fields = [
            "id", "product", "product_name", "description",
            "quantity", "unit_price", "discount", "tax", "total",
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True, default="")
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "branch", "branch_name", "customer", "customer_name",
            "invoice_number", "issue_date", "due_date",
            "subtotal", "discount", "tax", "total", "amount_paid",
            "balance_due", "status", "notes", "items",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class InvoiceItemInputSerializer(serializers.Serializer):
    product_id = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    unit_price = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    discount = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=0, min_value=0
    )


class InvoiceCreateSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField()
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    items = InvoiceItemInputSerializer(many=True)
    discount = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=0, min_value=0
    )
    due_date = serializers.DateField(required=False, allow_null=True)
    issue_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    issue_immediately = serializers.BooleanField(default=False)
