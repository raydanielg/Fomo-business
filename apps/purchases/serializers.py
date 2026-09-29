from decimal import Decimal
from rest_framework import serializers

from .models import Purchase, PurchaseItem


class PurchaseItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = PurchaseItem
        fields = ["id", "product", "product_name", "quantity", "unit_cost", "total"]


class PurchaseSerializer(serializers.ModelSerializer):
    items = PurchaseItemSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True, default="")
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Purchase
        fields = [
            "id", "branch", "branch_name", "supplier", "supplier_name",
            "reference", "subtotal", "tax", "total", "status",
            "received_at", "notes", "items", "created_at", "updated_at",
        ]
        read_only_fields = fields


class PurchaseItemInputSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    unit_cost = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)


class PurchaseCreateSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField()
    supplier_id = serializers.UUIDField(required=False, allow_null=True)
    items = PurchaseItemInputSerializer(many=True)
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    receive_immediately = serializers.BooleanField(default=True)
