from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.mixins import TenantScopedQuerySetMixin
from apps.common.permissions import HasActiveMembership, HasPermission
from apps.roles.models import Role

from .models import Membership
from .serializers import (
    InviteSerializer,
    MembershipSerializer,
    MembershipUpdateSerializer,
    RoleSerializer,
)
from . import services


class MembershipViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    queryset = Membership.objects.none()
    """Staff management for the current business."""

    permission_classes = [HasActiveMembership, HasPermission]
    permission_map = {
        "list": "staff.view",
        "retrieve": "staff.view",
        "invite": "staff.invite",
        "update": "staff.update",
        "partial_update": "staff.update",
        "destroy": "staff.remove",
    }
    filterset_fields = ["status"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    ordering_fields = ["created_at", "joined_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Membership.objects.none()
        return (
            Membership.objects.filter(business=self.request.business)
            .select_related("user", "role")
            .prefetch_related("allowed_branches")
        )

    def get_serializer_class(self):
        if self.action == "invite":
            return InviteSerializer
        if self.action in ("update", "partial_update"):
            return MembershipUpdateSerializer
        return MembershipSerializer

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        """The caller's own membership context — drives permission-aware UI."""
        return Response(
            {"success": True,
             "data": MembershipSerializer(request.membership).data}
        )

    @action(detail=False, methods=["post"], url_path="invite")
    def invite(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = services.invite_member(
            business=request.business,
            invited_by=request.user,
            **serializer.validated_data,
        )
        return Response(
            {"success": True, "data": MembershipSerializer(membership).data},
            status=201,
        )

    def perform_update(self, serializer):
        services.update_membership(
            membership=self.get_object(),
            actor=self.request.user,
            role_id=self.request.data.get("role"),
            status=serializer.validated_data.get("status"),
            allowed_branch_ids=(
                [str(b.id) for b in serializer.validated_data["allowed_branches"]]
                if "allowed_branches" in serializer.validated_data
                else None
            ),
        )

    def destroy(self, request, *args, **kwargs):
        services.remove_membership(membership=self.get_object(), actor=request.user)
        return Response({"success": True, "message": "Member removed."})


class RoleViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    queryset = Role.objects.none()
    """Roles of the current business. System roles are read-only."""

    permission_classes = [HasActiveMembership, HasPermission]
    serializer_class = RoleSerializer
    permission_map = {
        "list": "staff.view",
        "retrieve": "staff.view",
        "create": "staff.update",
        "update": "staff.update",
        "partial_update": "staff.update",
        "destroy": "staff.update",
    }

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Role.objects.none()
        return Role.objects.filter(business=self.request.business)

    def perform_destroy(self, instance):
        if instance.is_system:
            from apps.common.exceptions import APIError, ErrorCode

            raise APIError(
                "System roles cannot be deleted.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )
        instance.delete()


class MyMembershipViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Membership.objects.none()
    """The authenticated user's memberships across businesses."""

    serializer_class = MembershipSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Membership.objects.none()
        return Membership.objects.filter(user=self.request.user).select_related(
            "business", "role", "user"
        )

    @action(detail=True, methods=["post"], url_path="accept")
    def accept(self, request, pk=None):
        membership = services.accept_invitation(user=request.user, business_id=pk)
        return Response(
            {"success": True, "data": MembershipSerializer(membership).data}
        )
