"""InvoiceService — numbering, totals, lifecycle."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services import log as audit_log
from apps.common.exceptions import APIError, ErrorCode

from .models import Invoice, InvoiceItem

ZERO = Decimal("0")
CENT = Decimal("0.01")


def _money(v):
    return Decimal(str(v)).quantize(CENT)


def generate_invoice_number(business):
    """Sequential per-business invoice number, race-safe."""
    locked = business.__class__.objects.select_for_update().get(id=business.id)
    seq = int(locked.settings.get("invoice_seq", 0)) + 1
    locked.settings["invoice_seq"] = seq
    locked.save(update_fields=["settings"])
    return f"INV-{seq:08d}"


@transaction.atomic
def create_invoice(*, business, branch, user, items_data, customer=None,
                   discount=ZERO, due_date=None, issue_date=None, notes=""):
    if not items_data:
        raise APIError("An invoice requires at least one item.",
                       code=ErrorCode.VALIDATION_ERROR)

    subtotal = ZERO
    total_tax = ZERO
    items = []

    for entry in items_data:
        quantity = Decimal(str(entry["quantity"]))
        unit_price = _money(entry["unit_price"])
        discount_line = _money(entry.get("discount", ZERO))
        description = entry.get("description", "")
        product = entry.get("product")

        line_base = _money(quantity * unit_price)
        line_subtotal = line_base - discount_line
        if line_subtotal < 0:
            raise APIError("Line discount exceeds line total.",
                           code=ErrorCode.VALIDATION_ERROR)
        tax_rate = product.tax_rate if product else Decimal("0")
        line_tax = _money(line_subtotal * tax_rate / 100)
        line_total = line_subtotal + line_tax

        items.append({
            "product": product,
            "description": description or (product.name if product else ""),
            "quantity": quantity,
            "unit_price": unit_price,
            "discount": discount_line,
            "tax": line_tax,
            "total": line_total,
        })
        subtotal += line_subtotal
        total_tax += line_tax

    discount = _money(discount)
    if discount < 0 or discount > subtotal:
        raise APIError("Invoice discount is invalid.", code=ErrorCode.VALIDATION_ERROR)

    tax_on_discounted = _money(
        total_tax * (subtotal - discount) / subtotal
    ) if subtotal else ZERO
    total = _money(subtotal - discount + tax_on_discounted)

    invoice = Invoice.objects.create(
        business=business,
        branch=branch,
        customer=customer,
        invoice_number=generate_invoice_number(business),
        issue_date=issue_date or timezone.now().date(),
        due_date=due_date,
        subtotal=subtotal,
        discount=discount,
        tax=tax_on_discounted,
        total=total,
        balance_due=total,
        status=Invoice.Status.DRAFT,
        notes=notes,
        created_by=user,
    )
    InvoiceItem.objects.bulk_create(InvoiceItem(invoice=invoice, **i) for i in items)

    audit_log(
        AuditLog.Action.INVOICE_CREATED,
        business=business, user=user,
        resource_type="Invoice", resource_id=invoice.id,
        new_values={"invoice_number": invoice.invoice_number, "total": str(total)},
    )
    return invoice


@transaction.atomic
def issue_invoice(*, invoice, user=None):
    invoice = Invoice.objects.select_for_update().get(id=invoice.id)
    if invoice.status != Invoice.Status.DRAFT:
        raise APIError("Only draft invoices can be issued.",
                       code=ErrorCode.INVALID_STATE_TRANSITION, status_code=409)
    invoice.status = Invoice.Status.ISSUED
    if invoice.customer:
        customer = invoice.customer.__class__.objects.select_for_update().get(
            id=invoice.customer.id
        )
        customer.current_balance += invoice.balance_due
        customer.save(update_fields=["current_balance", "updated_at"])
    invoice.save(update_fields=["status", "updated_at"])
    audit_log(
        AuditLog.Action.INVOICE_UPDATED,
        business=invoice.business, user=user,
        resource_type="Invoice", resource_id=invoice.id,
        new_values={"status": "issued"},
    )
    return invoice


@transaction.atomic
def cancel_invoice(*, invoice, user=None):
    invoice = Invoice.objects.select_for_update().get(id=invoice.id)
    if invoice.status == Invoice.Status.PAID:
        raise APIError("Paid invoices cannot be cancelled.",
                       code=ErrorCode.INVOICE_ALREADY_PAID, status_code=409)
    if invoice.status == Invoice.Status.CANCELLED:
        raise APIError("Invoice is already cancelled.",
                       code=ErrorCode.INVOICE_CANCELLED, status_code=409)
    # Revert the customer balance for the unpaid portion
    if invoice.customer and invoice.balance_due > 0:
        customer = invoice.customer.__class__.objects.select_for_update().get(
            id=invoice.customer.id
        )
        customer.current_balance -= invoice.balance_due
        if customer.current_balance < 0:
            customer.current_balance = Decimal("0")
        customer.save(update_fields=["current_balance", "updated_at"])
    invoice.status = Invoice.Status.CANCELLED
    invoice.save(update_fields=["status", "updated_at"])
    audit_log(
        AuditLog.Action.INVOICE_CANCELLED,
        business=invoice.business, user=user,
        resource_type="Invoice", resource_id=invoice.id,
    )
    return invoice
