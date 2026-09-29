from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.branches.models import Branch
from apps.common.exceptions import APIError, ErrorCode
from apps.common.mixins import TenantScopedQuerySetMixin
from apps.common.permissions import HasActiveMembership, HasPermission
from apps.suppliers.models import Supplier

from .models import Purchase
from .serializers import PurchaseCreateSerializer, PurchaseSerializer
from . import services


class PurchaseViewSet(TenantScopedQuerySetMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = PurchaseSerializer
    queryset = Purchase.objects.none()
    permission_classes = [HasActiveMembership, HasPermission]
    permission_map = {
        "list": "purchases.view",
        "retrieve": "purchases.view",
        "create": "purchases.create",
        "receive": "purchases.update",
        "cancel": "purchases.delete",
    }
    filterset_fields = ["status", "branch", "supplier"]
    search_fields = ["reference", "supplier__name"]
    ordering_fields = ["created_at", "total"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Purchase.objects.none()
        return (
            Purchase.objects.filter(business=self.request.business)
            .select_related("branch", "supplier")
            .prefetch_related("items__product")
        )

    def create(self, request, *args, **kwargs):
        serializer = PurchaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        branch = Branch.objects.filter(
            id=data["branch_id"], business=request.business
        ).first()
        if branch is None:
            raise APIError("Branch not found.", code=ErrorCode.NOT_FOUND, status_code=404)
        if not request.membership.can_access_branch(branch.id):
            raise APIError("No access to this branch.",
                           code=ErrorCode.PERMISSION_DENIED, status_code=403)

        supplier = None
        if data.get("supplier_id"):
            supplier = Supplier.objects.filter(
                id=data["supplier_id"], business=request.business
            ).first()
            if supplier is None:
                raise APIError("Supplier not found.", code=ErrorCode.NOT_FOUND,
                               status_code=404)

        purchase = services.create_purchase(
            business=request.business, branch=branch, user=request.user,
            items_data=data["items"], supplier=supplier,
            reference=data.get("reference", ""), notes=data.get("notes", ""),
            receive_immediately=data.get("receive_immediately", True),
        )
        return Response(
            {"success": True, "data": PurchaseSerializer(purchase).data}, status=201
        )

    @action(detail=True, methods=["post"], url_path="receive")
    def receive(self, request, pk=None):
        purchase = services.receive_purchase(purchase=self.get_object(), user=request.user)
        return Response({"success": True, "data": PurchaseSerializer(purchase).data})

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        purchase = services.cancel_purchase(purchase=self.get_object(), user=request.user)
        return Response({"success": True, "data": PurchaseSerializer(purchase).data})
