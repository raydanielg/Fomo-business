from rest_framework import viewsets

from apps.common.mixins import TenantScopedQuerySetMixin
from apps.common.permissions import HasActiveMembership, HasPermission

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(TenantScopedQuerySetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.none()
    serializer_class = AuditLogSerializer
    permission_classes = [HasActiveMembership, HasPermission]
    required_permission = "audit.view"
    filterset_fields = ["action", "resource_type", "user"]
    search_fields = ["resource_id", "request_id"]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AuditLog.objects.none()
        return AuditLog.objects.filter(
            business=self.request.business
        ).select_related("user")
