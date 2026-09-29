from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from apps.branches.models import Branch
from apps.branches.serializers import BranchSerializer
from apps.roles.models import Role

from .models import Membership


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = [
            "id", "code", "name", "description", "permissions",
            "report_scope", "is_system",
        ]
        read_only_fields = ["id", "is_system"]


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    role = RoleSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(), source="role", write_only=True, required=False
    )
    allowed_branches = BranchSerializer(many=True, read_only=True)
    allowed_branch_ids = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(),
        source="allowed_branches",
        many=True,
        write_only=True,
        required=False,
    )

    class Meta:
        model = Membership
        fields = [
            "id",
            "user",
            "role",
            "role_id",
            "status",
            "allowed_branches",
            "allowed_branch_ids",
            "joined_at",
            "created_at",
        ]
        read_only_fields = ["id", "status", "joined_at", "created_at"]


class InviteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role_id = serializers.UUIDField()
    allowed_branch_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False
    )
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")


class MembershipUpdateSerializer(serializers.ModelSerializer):
    allowed_branch_ids = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(),
        source="allowed_branches",
        many=True,
        required=False,
    )

    class Meta:
        model = Membership
        fields = ["role", "status", "allowed_branch_ids"]
