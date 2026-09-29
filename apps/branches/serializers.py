from rest_framework import serializers

from .models import Branch


class BranchSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(
        source="manager.full_name", read_only=True, default=""
    )

    class Meta:
        model = Branch
        fields = [
            "id",
            "name",
            "code",
            "phone",
            "email",
            "address",
            "city",
            "region",
            "manager",
            "manager_name",
            "is_active",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_default", "created_at", "updated_at"]
