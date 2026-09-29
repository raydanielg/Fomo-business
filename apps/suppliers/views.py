from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.mixins import TenantScopedQuerySetMixin
from apps.common.permissions import HasActiveMembership, HasPermission

from .models import Supplier
from .serializers import SupplierSerializer


class SupplierViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    queryset = Supplier.objects.none()
    serializer_class = SupplierSerializer
    permission_classes = [HasActiveMembership, HasPermission]
    permission_map = {
        "list": "suppliers.view",
        "retrieve": "suppliers.view",
        "create": "suppliers.create",
        "update": "suppliers.update",
        "partial_update": "suppliers.update",
        "destroy": "suppliers.delete",
        "history": "suppliers.view",
    }
    filterset_fields = ["is_active"]
    search_fields = ["name", "phone", "email", "tax_number"]
    ordering_fields = ["name", "created_at", "balance"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Supplier.objects.none()
        return Supplier.objects.filter(business=self.request.business)

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        supplier = self.get_object()
        from apps.purchases.serializers import PurchaseSerializer

        purchases = supplier.purchases.select_related("branch").order_by("-created_at")[:100]
        return Response(
            {"success": True, "data": PurchaseSerializer(purchases, many=True).data}
        )
