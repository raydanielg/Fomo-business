from rest_framework import serializers

from .models import Supplier


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "id", "name", "phone", "email", "address", "tax_number",
            "notes", "balance", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "balance", "created_at", "updated_at"]
