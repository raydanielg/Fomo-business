from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.branches.models import Branch
from apps.common.exceptions import APIError, ErrorCode
from apps.common.mixins import TenantScopedQuerySetMixin
from apps.common.permissions import HasActiveMembership, HasPermission
from apps.customers.models import Customer
from apps.products.models import Product

from .models import Invoice
from .serializers import InvoiceCreateSerializer, InvoiceSerializer
from . import services


class InvoiceViewSet(TenantScopedQuerySetMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = InvoiceSerializer
    queryset = Invoice.objects.none()
    permission_classes = [HasActiveMembership, HasPermission]
    permission_map = {
        "list": "invoices.view",
        "retrieve": "invoices.view",
        "create": "invoices.create",
        "issue": "invoices.update",
        "cancel": "invoices.cancel",
        "pdf": "invoices.view",
        "record_payment": "payments.create",
    }
    filterset_fields = ["status", "branch", "customer"]
    search_fields = ["invoice_number", "customer__name"]
    ordering_fields = ["created_at", "due_date", "total"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Invoice.objects.none()
        return (
            Invoice.objects.filter(business=self.request.business)
            .select_related("branch", "customer")
            .prefetch_related("items__product")
        )

    def create(self, request, *args, **kwargs):
        serializer = InvoiceCreateSerializer(data=request.data)
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

        customer = None
        if data.get("customer_id"):
            customer = Customer.objects.filter(
                id=data["customer_id"], business=request.business
            ).first()
            if customer is None:
                raise APIError("Customer not found.", code=ErrorCode.NOT_FOUND,
                               status_code=404)

        # resolve products for invoice lines
        items_data = []
        for entry in data["items"]:
            product = None
            if entry.get("product_id"):
                product = Product.objects.filter(
                    id=entry["product_id"], business=request.business
                ).first()
                if product is None:
                    raise APIError("Product not found.",
                                   code=ErrorCode.PRODUCT_NOT_FOUND, status_code=404)
            entry["product"] = product
            items_data.append(entry)

        invoice = services.create_invoice(
            business=request.business, branch=branch, user=request.user,
            items_data=items_data, customer=customer,
            discount=data.get("discount", 0),
            due_date=data.get("due_date"), issue_date=data.get("issue_date"),
            notes=data.get("notes", ""),
        )
        if data.get("issue_immediately"):
            invoice = services.issue_invoice(invoice=invoice, user=request.user)

        return Response(
            {"success": True, "data": InvoiceSerializer(invoice).data}, status=201
        )

    @action(detail=True, methods=["get"], url_path="pdf")
    def pdf(self, request, pk=None):
        """A4 invoice PDF — generated on demand, cached under media/invoices/."""
        invoice = self.get_object()
        from .pdf import get_invoice_pdf

        pdf_bytes = get_invoice_pdf(invoice)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="invoice-{invoice.invoice_number}.pdf"'
        )
        return response

    @action(detail=True, methods=["post"], url_path="issue")
    def issue(self, request, pk=None):
        invoice = services.issue_invoice(invoice=self.get_object(), user=request.user)
        return Response({"success": True, "data": InvoiceSerializer(invoice).data})

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        invoice = services.cancel_invoice(invoice=self.get_object(), user=request.user)
        return Response({"success": True, "data": InvoiceSerializer(invoice).data})

    @action(detail=True, methods=["post"], url_path="record-payment")
    def record_payment(self, request, pk=None):
        from apps.payments.serializers import InvoicePaymentSerializer
        from apps.payments.services import record_payment

        serializer = InvoicePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = record_payment(
            business=request.business,
            invoice=self.get_object(),
            amount=serializer.validated_data["amount"],
            method=serializer.validated_data["method"],
            reference=serializer.validated_data.get("reference", ""),
            received_by=request.user,
        )
        from apps.payments.serializers import PaymentSerializer

        return Response(
            {"success": True, "data": PaymentSerializer(payment).data}, status=201
        )
