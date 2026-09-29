from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True, default="")

    class Meta:
        model = AuditLog
        fields = [
            "id", "user", "user_email", "action", "resource_type",
            "resource_id", "old_values", "new_values",
            "ip_address", "user_agent", "request_id", "created_at",
        ]
        read_only_fields = fields
