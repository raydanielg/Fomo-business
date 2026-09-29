from rest_framework import viewsets

from apps.common.mixins import TenantScopedQuerySetMixin
from apps.common.permissions import HasActiveMembership, HasPermission
from apps.subscriptions.services import enforce_limit

from .models import Branch
from .serializers import BranchSerializer


class BranchViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    serializer_class = BranchSerializer
    permission_classes = [HasActiveMembership, HasPermission]
    permission_map = {
        "list": "branches.view",
        "retrieve": "branches.view",
        "create": "branches.create",
        "update": "branches.update",
        "partial_update": "branches.update",
        "destroy": "branches.delete",
    }
    filterset_fields = ["is_active"]
    search_fields = ["name", "code", "city"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        qs = Branch.objects.filter(business=self.request.business)
        membership = self.request.membership
        if membership and membership.allowed_branches.exists():
            qs = qs.filter(id__in=membership.allowed_branches.values("id"))
        return qs.select_related("manager")

    def perform_create(self, serializer):
        count = Branch.objects.filter(business=self.request.business).count()
        enforce_limit(self.request.business, "max_branches", current_value=count)
        serializer.save(business=self.request.business)
