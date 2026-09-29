from decimal import Decimal
from rest_framework import serializers

from apps.branches.models import Branch
from apps.products.models import Product

from .models import InventoryMovement, StockLevel


class StockLevelSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    low_stock_level = serializers.DecimalField(
        source="product.low_stock_threshold",
        max_digits=14,
        decimal_places=3,
        read_only=True,
    )

    class Meta:
        model = StockLevel
        fields = [
            "id", "product", "product_name", "product_sku",
            "branch", "branch_name", "quantity", "low_stock_level",
            "updated_at",
        ]
        read_only_fields = fields


class InventoryMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    created_by_email = serializers.CharField(source="created_by.email", read_only=True, default="")

    class Meta:
        model = InventoryMovement
        fields = [
            "id", "branch", "branch_name", "product", "product_name",
            "movement_type", "quantity", "unit_cost", "reference_type",
            "reference_id", "note", "balance_after", "created_by",
            "created_by_email", "created_at",
        ]
        read_only_fields = fields


class AdjustmentSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    branch_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    direction = serializers.ChoiceField(choices=["in", "out"])
    note = serializers.CharField(required=False, allow_blank=True, default="")


class TransferSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    from_branch_id = serializers.UUIDField()
    to_branch_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    note = serializers.CharField(required=False, allow_blank=True, default="")
