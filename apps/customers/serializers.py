from rest_framework import serializers

from .models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "id", "name", "phone", "email", "address", "notes",
            "credit_limit", "current_balance", "is_active",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "current_balance", "created_at", "updated_at"]
