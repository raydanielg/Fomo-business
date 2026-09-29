from rest_framework import permissions, viewsets
from rest_framework.response import Response

from apps.audit.models import AuditLog
from apps.audit.services import log as audit_log
from apps.common.exceptions import APIError, ErrorCode
from apps.common.mixins import TenantScopedQuerySetMixin
from apps.common.permissions import HasActiveMembership, HasPermission

from .models import Business
from .serializers import (
    BusinessCreateSerializer,
    BusinessSerializer,
    BusinessUpdateSerializer,
)
from .services import create_business


class BusinessViewSet(viewsets.ModelViewSet):
    queryset = Business.objects.none()
    """
    list   → businesses the user belongs to
    create → provision a new tenant
    retrieve/update → only via active membership context (X-Business-ID)
    """

    def get_serializer_class(self):
        if self.action == "create":
            return BusinessCreateSerializer
        if self.action in ("update", "partial_update"):
            return BusinessUpdateSerializer
        return BusinessSerializer

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated()]
        if self.action == "list":
            return [permissions.IsAuthenticated()]
        return [HasActiveMembership(), HasPermission()]

    permission_map = {
        "retrieve": "settings.view",
        "update": "settings.update",
        "partial_update": "settings.update",
        "destroy": "settings.update",
    }

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Business.objects.none()
        if self.action == "list":
            return Business.objects.filter(
                memberships__user=self.request.user,
                memberships__status="active",
            ).distinct()
        # tenant-scoped: only ever the current business
        business = getattr(self.request, "business", None)
        if business is None:
            return Business.objects.none()
        return Business.objects.filter(id=business.id)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        business = create_business(
            owner=request.user, **serializer.validated_data
        )
        audit_log(
            AuditLog.Action.MEMBERSHIP_CREATED,
            business=business,
            user=request.user,
            resource_type="Business",
            resource_id=business.id,
        )
        return Response(
            {"success": True, "data": BusinessSerializer(business).data},
            status=201,
        )

    def perform_update(self, serializer):
        old = BusinessSerializer(self.get_object()).data
        instance = serializer.save()
        audit_log(
            AuditLog.Action.BUSINESS_UPDATED,
            business=instance,
            user=self.request.user,
            resource_type="Business",
            resource_id=instance.id,
            old_values=old,
            new_values=BusinessSerializer(instance).data,
        )

    def destroy(self, request, *args, **kwargs):
        # Businesses are not hard-deleted via API; require suspension path.
        raise APIError(
            "Businesses cannot be deleted via API. Contact support to close a business.",
            code=ErrorCode.PERMISSION_DENIED,
            status_code=403,
        )
