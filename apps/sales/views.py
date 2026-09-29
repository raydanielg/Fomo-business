from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.branches.models import Branch
from apps.common.exceptions import APIError, ErrorCode
from apps.common.mixins import TenantScopedQuerySetMixin
from apps.common.permissions import HasActiveMembership, HasPermission
from apps.customers.models import Customer

from .models import Sale
from .serializers import (
    PaymentInputSerializer,
    SaleActionSerializer,
    SaleCreateSerializer,
    SaleSerializer,
)
from . import services


class SaleViewSet(TenantScopedQuerySetMixin, viewsets.ReadOnlyModelViewSet):
    """Sales are created/completed via actions, never generic PATCH."""

    serializer_class = SaleSerializer
    queryset = Sale.objects.none()  # for schema; get_queryset enforces tenant
    permission_classes = [HasActiveMembership, HasPermission]
    permission_map = {
        "list": "sales.view",
        "retrieve": "sales.view",
        "create": "sales.create",
        "complete": "sales.create",
        "cancel": "sales.cancel",
        "refund": "sales.refund",
        "receipt": "sales.view",
    }
    filterset_fields = ["status", "payment_status", "branch", "customer", "cashier"]
    search_fields = ["receipt_number", "customer__name", "notes"]
    ordering_fields = ["created_at", "total"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Sale.objects.none()
        qs = (
            Sale.objects.filter(business=self.request.business)
            .prefetch_related("payments")
            .select_related("branch", "customer", "cashier")
            .prefetch_related("items__product")
        )
        membership = self.request.membership
        if membership and membership.allowed_branches.exists():
            qs = qs.filter(branch__in=membership.allowed_branches.all())
        return qs

    def _resolve_branch(self, branch_id):
        branch = Branch.objects.filter(
            id=branch_id, business=self.request.business
        ).first()
        if branch is None:
            raise APIError("Branch not found.", code=ErrorCode.NOT_FOUND, status_code=404)
        if not self.request.membership.can_access_branch(branch.id):
            raise APIError("No access to this branch.",
                           code=ErrorCode.PERMISSION_DENIED, status_code=403)
        return branch

    def create(self, request, *args, **kwargs):
        serializer = SaleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        branch = self._resolve_branch(data["branch_id"])
        customer = None
        if data.get("customer_id"):
            customer = Customer.objects.filter(
                id=data["customer_id"], business=request.business
            ).first()
            if customer is None:
                raise APIError("Customer not found.", code=ErrorCode.NOT_FOUND,
                               status_code=404)

        sale = services.create_sale(
            business=request.business,
            branch=branch,
            user=request.user,
            items_data=data["items"],
            customer=customer,
            discount=data.get("discount", 0),
            notes=data.get("notes", ""),
            payment=data.get("payment"),
            status="draft" if data.get("draft") else "completed",
        )
        return Response(
            {"success": True, "data": SaleSerializer(sale).data}, status=201
        )

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        payment = request.data.get("payment")
        if payment:
            serializer = PaymentInputSerializer(data=payment)
            serializer.is_valid(raise_exception=True)
            payment = serializer.validated_data
        sale = services.complete_sale(
            sale=self.get_object(), payment=payment, user=request.user
        )
        return Response({"success": True, "data": SaleSerializer(sale).data})

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        serializer = SaleActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = services.cancel_sale(
            sale=self.get_object(), user=request.user,
            reason=serializer.validated_data.get("reason", ""),
        )
        return Response({"success": True, "data": SaleSerializer(sale).data})

    @action(detail=True, methods=["post"], url_path="refund")
    def refund(self, request, pk=None):
        serializer = SaleActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = services.refund_sale(
            sale=self.get_object(), user=request.user,
            reason=serializer.validated_data.get("reason", ""),
        )
        return Response({"success": True, "data": SaleSerializer(sale).data})

    @action(detail=True, methods=["get"], url_path="receipt")
    def receipt(self, request, pk=None):
        """PDF receipt — generated on demand, cached under media/receipts/."""
        sale = self.get_object()
        if sale.status != Sale.Status.COMPLETED:
            raise APIError("Receipts are only available for completed sales.",
                           code=ErrorCode.INVALID_STATE_TRANSITION, status_code=409)
        from .receipts import get_receipt_pdf

        pdf_bytes = get_receipt_pdf(sale)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="receipt-{sale.receipt_number}.pdf"'
        )
        return response
