"""PaymentService — record payments, keep sale/invoice/customer balances true."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services import log as audit_log
from apps.common.exceptions import APIError, ErrorCode

from .models import Payment

CENT = Decimal("0.01")


def _money(value):
    return Decimal(str(value)).quantize(CENT)


@transaction.atomic
def record_payment(*, business, amount, method, sale=None, invoice=None,
                   customer=None, branch=None, reference="", received_by=None,
                   metadata=None):
    """
    Record a payment against a sale/invoice/customer.
    Updates the linked document's amount_paid / balance_due / payment_status
    inside the same transaction. Amounts are validated server-side.
    """
    amount = _money(amount)
    if amount <= 0:
        raise APIError("Payment amount must be positive.",
                       code=ErrorCode.INVALID_PAYMENT_AMOUNT)

    if sale is not None:
        sale = sale.__class__.objects.select_for_update().get(id=sale.id)
        if sale.status not in (sale.Status.COMPLETED,):
            raise APIError("Payments can only be recorded on completed sales.",
                           code=ErrorCode.INVALID_STATE_TRANSITION, status_code=409)
        outstanding = sale.total - sale.amount_paid
        if amount > outstanding:
            raise APIError(
                f"Payment exceeds outstanding balance ({outstanding}).",
                code=ErrorCode.INVALID_PAYMENT_AMOUNT,
            )
        sale.amount_paid += amount
        sale.balance_due = sale.total - sale.amount_paid
        sale.payment_status = (
            sale.PaymentStatus.PAID if sale.balance_due <= 0 else sale.PaymentStatus.PARTIAL
        )
        sale.save(update_fields=["amount_paid", "balance_due", "payment_status", "updated_at"])
        customer = customer or sale.customer

    if invoice is not None:
        invoice = invoice.__class__.objects.select_for_update().get(id=invoice.id)
        if invoice.status in (invoice.Status.PAID, invoice.Status.CANCELLED):
            code = (ErrorCode.INVOICE_ALREADY_PAID if invoice.status == invoice.Status.PAID
                    else ErrorCode.INVOICE_CANCELLED)
            raise APIError("Invoice cannot accept payments.", code=code, status_code=409)
        outstanding = invoice.total - invoice.amount_paid
        if amount > outstanding:
            raise APIError(
                f"Payment exceeds invoice balance ({outstanding}).",
                code=ErrorCode.INVALID_PAYMENT_AMOUNT,
            )
        invoice.amount_paid += amount
        invoice.balance_due = invoice.total - invoice.amount_paid
        invoice.status = (
            invoice.Status.PAID if invoice.balance_due <= 0 else invoice.Status.PARTIALLY_PAID
        )
        invoice.save(update_fields=["amount_paid", "balance_due", "status", "updated_at"])
        customer = customer or invoice.customer

    if customer is not None:
        customer = customer.__class__.objects.select_for_update().get(id=customer.id)
        customer.current_balance = customer.current_balance - amount
        if customer.current_balance < 0:
            customer.current_balance = Decimal("0")
        customer.save(update_fields=["current_balance", "updated_at"])

    payment = Payment.objects.create(
        business=business,
        branch=branch or (sale.branch if sale else (invoice.branch if invoice else None)),
        sale=sale,
        invoice=invoice,
        customer=customer,
        amount=amount,
        method=method,
        reference=reference,
        status=Payment.Status.COMPLETED,
        paid_at=timezone.now(),
        received_by=received_by,
        metadata=metadata or {},
    )

    audit_log(
        AuditLog.Action.PAYMENT_RECEIVED,
        business=business, user=received_by,
        resource_type="Payment", resource_id=payment.id,
        new_values={"amount": str(amount), "method": method},
    )

    try:
        from apps.notifications.models import Notification
        from apps.notifications.services import notify_business_members

        notify_business_members(
            business,
            type=Notification.Type.PAYMENT_RECEIVED,
            title="Payment received",
            message=f"{amount} received via {method}.",
            data={"payment_id": str(payment.id)},
            permission="payments.view",
        )
    except Exception:
        pass

    return payment
