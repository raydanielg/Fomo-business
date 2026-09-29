from rest_framework import serializers

from .models import Category, Product, Unit


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "description", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id", "name", "abbreviation"]
        read_only_fields = ["id"]


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    unit_abbreviation = serializers.CharField(source="unit.abbreviation", read_only=True, default="")

    class Meta:
        model = Product
        fields = [
            "id", "name", "category", "category_name", "sku", "barcode",
            "description", "buying_price", "selling_price", "cost_price",
            "tax_rate", "track_inventory", "low_stock_threshold",
            "unit", "unit_abbreviation", "image", "is_active",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        business = self.context["business"]
        # Cross-field uniqueness pre-checks produce friendlier errors than the DB
        sku = attrs.get("sku")
        if sku:
            qs = Product.objects.filter(business=business, sku=sku)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"sku": "A product with this SKU already exists."}
                )
        barcode = attrs.get("barcode")
        if barcode:
            qs = Product.objects.filter(business=business, barcode=barcode)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"barcode": "A product with this barcode already exists."}
                )
        return attrs


class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    # annotated in ProductViewSet.get_queryset — total across all branches,
    # or per-branch when ?branch= is given
    total_stock = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True, default=None,
        allow_null=True,
    )

    class Meta:
        model = Product
        fields = [
            "id", "name", "category_name", "sku", "barcode",
            "selling_price", "cost_price", "tax_rate",
            "track_inventory", "low_stock_threshold", "is_active",
            "total_stock",
        ]
