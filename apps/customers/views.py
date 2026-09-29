from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.mixins import TenantScopedQuerySetMixin
from apps.common.permissions import HasActiveMembership, HasPermission

from .models import Customer
from .serializers import CustomerSerializer


class CustomerViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    queryset = Customer.objects.none()
    serializer_class = CustomerSerializer
    permission_classes = [HasActiveMembership, HasPermission]
    permission_map = {
        "list": "customers.view",
        "retrieve": "customers.view",
        "create": "customers.create",
        "update": "customers.update",
        "partial_update": "customers.update",
        "destroy": "customers.delete",
        "history": "customers.view",
        "payments": "payments.view",
    }
    filterset_fields = ["is_active"]
    search_fields = ["name", "phone", "email"]
    ordering_fields = ["name", "created_at", "current_balance"]

    WALK_IN_NAME = "Walk-in Customer"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Customer.objects.none()
        return Customer.objects.filter(business=self.request.business)

    def _ensure_walk_in(self):
        # Every business gets a built-in counter-sale customer — POS can
        # always complete a sale without creating a customer record.
        Customer.objects.get_or_create(
            business=self.request.business,
            name=self.WALK_IN_NAME,
            defaults={"notes": "Default customer for counter sales"},
        )

    def list(self, request, *args, **kwargs):
        self._ensure_walk_in()
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        customer = self.get_object()
        from apps.sales.serializers import SaleSerializer

        sales = customer.sales.select_related("branch", "cashier").order_by("-created_at")[:100]
        return Response({"success": True, "data": SaleSerializer(sales, many=True).data})

    @action(detail=True, methods=["get"], url_path="payments")
    def payments(self, request, pk=None):
        customer = self.get_object()
        from apps.payments.serializers import PaymentSerializer

        payments = customer.payments.order_by("-paid_at")[:100]
        return Response({"success": True, "data": PaymentSerializer(payments, many=True).data})
