from rest_framework import viewsets
from rest_framework.response import Response

from apps.branches.models import Branch
from apps.common.exceptions import APIError, ErrorCode
from apps.common.mixins import TenantScopedQuerySetMixin
from apps.common.permissions import HasActiveMembership, HasPermission
from apps.customers.models import Customer
from apps.invoices.models import Invoice
from apps.sales.models import Sale

from .models import Payment
from .serializers import PaymentSerializer, RecordPaymentSerializer
from . import services


class PaymentViewSet(TenantScopedQuerySetMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    queryset = Payment.objects.none()
    permission_classes = [HasActiveMembership, HasPermission]
    permission_map = {
        "list": "payments.view",
        "retrieve": "payments.view",
        "create": "payments.create",
    }
    filterset_fields = ["method", "status", "branch", "customer", "sale", "invoice"]
    search_fields = ["reference", "customer__name", "sale__receipt_number", "invoice__invoice_number"]
    ordering_fields = ["paid_at", "amount"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Payment.objects.none()
        return (
            Payment.objects.filter(business=self.request.business)
            .select_related("branch", "customer", "received_by")
        )

    def create(self, request, *args, **kwargs):
        serializer = RecordPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        sale = invoice = customer = branch = None
        if data.get("sale_id"):
            sale = Sale.objects.filter(id=data["sale_id"], business=request.business).first()
            if sale is None:
                raise APIError("Sale not found.", code=ErrorCode.NOT_FOUND, status_code=404)
        if data.get("invoice_id"):
            invoice = Invoice.objects.filter(id=data["invoice_id"], business=request.business).first()
            if invoice is None:
                raise APIError("Invoice not found.", code=ErrorCode.NOT_FOUND, status_code=404)
        if data.get("customer_id"):
            customer = Customer.objects.filter(id=data["customer_id"], business=request.business).first()
            if customer is None:
                raise APIError("Customer not found.", code=ErrorCode.NOT_FOUND, status_code=404)
        if data.get("branch_id"):
            branch = Branch.objects.filter(id=data["branch_id"], business=request.business).first()
            if branch is None:
                raise APIError("Branch not found.", code=ErrorCode.NOT_FOUND, status_code=404)

        payment = services.record_payment(
            business=request.business,
            sale=sale, invoice=invoice, customer=customer, branch=branch,
            amount=data["amount"], method=data["method"],
            reference=data.get("reference", ""), received_by=request.user,
        )
        return Response(
            {"success": True, "data": PaymentSerializer(payment).data}, status=201
        )
