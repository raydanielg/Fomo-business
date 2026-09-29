from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.branches.models import Branch
from apps.common.exceptions import APIError, ErrorCode
from apps.common.mixins import TenantScopedQuerySetMixin
from apps.common.permissions import HasActiveMembership, HasPermission
from apps.products.models import Product

from .models import InventoryMovement, StockLevel
from .serializers import (
    AdjustmentSerializer,
    InventoryMovementSerializer,
    StockLevelSerializer,
    TransferSerializer,
)
from . import services


def _resolve_branch(request, branch_id):
    branch = Branch.objects.filter(
        id=branch_id, business=request.business
    ).first()
    if branch is None:
        raise APIError("Branch not found.", code=ErrorCode.NOT_FOUND, status_code=404)
    membership = request.membership
    if membership and not membership.can_access_branch(branch.id):
        raise APIError("No access to this branch.",
                       code=ErrorCode.PERMISSION_DENIED, status_code=403)
    return branch


class StockLevelViewSet(TenantScopedQuerySetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = StockLevel.objects.none()
    serializer_class = StockLevelSerializer
    permission_classes = [HasActiveMembership, HasPermission]
    required_permission = "inventory.view"
    filterset_fields = ["branch", "product"]
    ordering_fields = ["quantity", "updated_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return StockLevel.objects.none()
        qs = StockLevel.objects.filter(
            business=self.request.business
        ).select_related("product", "branch")
        membership = self.request.membership
        if membership and membership.allowed_branches.exists():
            qs = qs.filter(branch__in=membership.allowed_branches.all())
        return qs


class InventoryMovementViewSet(TenantScopedQuerySetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = InventoryMovement.objects.none()
    serializer_class = InventoryMovementSerializer
    permission_classes = [HasActiveMembership, HasPermission]
    required_permission = "inventory.view"
    filterset_fields = ["movement_type", "branch", "product"]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return InventoryMovement.objects.none()
        qs = InventoryMovement.objects.filter(
            business=self.request.business
        ).select_related("product", "branch", "created_by")
        membership = self.request.membership
        if membership and membership.allowed_branches.exists():
            qs = qs.filter(branch__in=membership.allowed_branches.all())
        return qs


class StockAdjustmentView(APIView):
    permission_classes = [HasActiveMembership, HasPermission]
    required_permission = "inventory.adjust"
    serializer_class = AdjustmentSerializer

    def post(self, request):
        serializer = AdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        product = Product.objects.filter(
            id=data["product_id"], business=request.business
        ).first()
        if product is None:
            raise APIError("Product not found.", code=ErrorCode.PRODUCT_NOT_FOUND,
                           status_code=404)
        branch = _resolve_branch(request, data["branch_id"])

        movement = services.adjust_stock(
            business=request.business, branch=branch, product=product,
            quantity=data["quantity"], direction=data["direction"],
            note=data["note"], user=request.user,
        )
        return Response(
            {"success": True, "data": InventoryMovementSerializer(movement).data},
            status=201,
        )


class StockTransferView(APIView):
    permission_classes = [HasActiveMembership, HasPermission]
    required_permission = "inventory.transfer"
    serializer_class = TransferSerializer

    def post(self, request):
        serializer = TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        product = Product.objects.filter(
            id=data["product_id"], business=request.business
        ).first()
        if product is None:
            raise APIError("Product not found.", code=ErrorCode.PRODUCT_NOT_FOUND,
                           status_code=404)
        from_branch = _resolve_branch(request, data["from_branch_id"])
        to_branch = _resolve_branch(request, data["to_branch_id"])

        out, in_ = services.transfer_stock(
            business=request.business, from_branch=from_branch,
            to_branch=to_branch, product=product,
            quantity=data["quantity"], note=data["note"], user=request.user,
        )
        return Response(
            {"success": True, "data": {
                "out": InventoryMovementSerializer(out).data,
                "in": InventoryMovementSerializer(in_).data,
            }},
            status=201,
        )
