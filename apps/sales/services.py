"""SaleService — server-side truth for totals + stock + payment.

Views are thin; all money/stock math happens here inside transaction.atomic.
Totals are computed from the product catalog, never trusted from the client.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services import log as audit_log
from apps.common.exceptions import APIError, ErrorCode
from apps.inventory import services as inventory_services
from apps.products.models import Product

from .models import Sale, SaleItem

logger = logging.getLogger("fomo.sales")

ZERO = Decimal("0")
CENT = Decimal("0.01")


def _money(value):
    return Decimal(str(value)).quantize(CENT)


def generate_receipt_number(business):
    """Sequential per-business receipt number, race-safe via the locked row."""
    from apps.businesses.models import Business

    # Lock the business row so concurrent cashiers can't collide
    locked = Business.objects.select_for_update().get(id=business.id)
    seq = int(locked.settings.get("receipt_seq", 0)) + 1
    locked.settings["receipt_seq"] = seq
    locked.save(update_fields=["settings"])
    return f"R-{seq:08d}"


def _price_items(business, items_data):
    """
    Resolve products and compute per-line totals server-side.
    Returns (items_to_create, subtotal, total_tax).
    """
    items = []
    subtotal = ZERO
    total_tax = ZERO

    for entry in items_data:
        product = (
            Product.objects.filter(business=business, id=entry["product_id"])
            .select_for_update()
            .first()
        )
        if product is None or not product.is_active:
            raise APIError(
                f"Product {entry['product_id']} not found or inactive.",
                code=ErrorCode.PRODUCT_NOT_FOUND,
                status_code=404,
            )

        quantity = Decimal(str(entry["quantity"]))
        # unit_price defaults to the catalog price; discounts come from input
        unit_price = _money(entry.get("unit_price", product.selling_price))
        discount = _money(entry.get("discount", ZERO))
        if discount < 0:
            raise APIError("Line discount cannot be negative.",
                           code=ErrorCode.VALIDATION_ERROR)

        line_base = _money(quantity * unit_price)
        line_subtotal = line_base - discount
        if line_subtotal < 0:
            raise APIError("Line discount exceeds line total.",
                           code=ErrorCode.VALIDATION_ERROR)

        line_tax = _money(line_subtotal * product.tax_rate / 100)
        line_total = line_subtotal + line_tax

        items.append(
            {
                "product": product,
                "quantity": quantity,
                "unit_price": unit_price,
                "discount": discount,
                "tax": line_tax,
                "total": line_total,
            }
        )
        subtotal += line_subtotal
        total_tax += line_tax

    return items, subtotal, total_tax


@transaction.atomic
def create_sale(*, business, branch, user, items_data, customer=None,
                discount=ZERO, notes="", payment=None, status="completed"):
    """
    Create a sale (draft or completed).

    payment: {"method": "CASH", "amount": "1000", "reference": "..."} or None
    """
    if not items_data:
        raise APIError("A sale requires at least one item.",
                       code=ErrorCode.VALIDATION_ERROR)

    items, subtotal, items_tax = _price_items(business, items_data)
    discount = _money(discount)
    if discount < 0 or discount > subtotal:
        raise APIError("Sale discount is invalid.", code=ErrorCode.VALIDATION_ERROR)

    tax_on_discounted = _money(
        items_tax * (subtotal - discount) / subtotal
    ) if subtotal else ZERO

    total = _money(subtotal - discount + tax_on_discounted)

    sale = Sale.objects.create(
        business=business,
        branch=branch,
        customer=customer,
        cashier=user,
        subtotal=subtotal,
        discount=discount,
        tax=tax_on_discounted,
        total=total,
        status=Sale.Status.DRAFT,
        notes=notes,
    )
    SaleItem.objects.bulk_create(
        SaleItem(sale=sale, **item) for item in items
    )

    if status == "completed":
        sale = complete_sale(sale=sale, payment=payment, user=user)

    audit_log(
        AuditLog.Action.SALE_CREATED,
        business=business, user=user,
        resource_type="Sale", resource_id=sale.id,
        new_values={"total": str(total), "items": len(items)},
    )
    return sale


@transaction.atomic
def complete_sale(*, sale, payment=None, user=None):
    """Finalize a draft sale: deduct stock, assign receipt, record payment."""
    sale = Sale.objects.select_for_update().get(id=sale.id)
    if sale.status == Sale.Status.COMPLETED:
        raise APIError("Sale is already completed.",
                       code=ErrorCode.SALE_ALREADY_COMPLETED, status_code=409)
    if sale.status != Sale.Status.DRAFT:
        raise APIError("Only draft sales can be completed.",
                       code=ErrorCode.SALE_NOT_COMPLETABLE, status_code=409)

    business = sale.business

    # Subscription: monthly sales limit
    from apps.subscriptions.models import UsageRecord
    from apps.subscriptions.services import enforce_limit, increment_usage

    sales_count = Sale.objects.filter(
        business=business,
        status=Sale.Status.COMPLETED,
        created_at__date__gte=timezone.now().date().replace(day=1),
    ).count()
    enforce_limit(business, "max_monthly_sales", current_value=sales_count)

    # Deduct stock (raises InsufficientStockError if not allowed)
    items = list(sale.items.select_related("product"))
    inventory_services.deduct_for_sale(
        business=business, branch=sale.branch, sale=sale, items=items, user=user
    )

    sale.receipt_number = generate_receipt_number(business)
    sale.status = Sale.Status.COMPLETED
    sale.save(update_fields=["status", "receipt_number", "updated_at"])

    if payment:
        from apps.payments.services import record_payment

        record_payment(
            business=business,
            sale=sale,
            branch=sale.branch,
            amount=payment["amount"],
            method=payment["method"],
            reference=payment.get("reference", ""),
            received_by=user,
        )
        sale.refresh_from_db(fields=["amount_paid", "balance_due", "payment_status"])
    increment_usage(business, UsageRecord.Metric.SALES_COUNT)

    audit_log(
        AuditLog.Action.SALE_COMPLETED,
        business=business, user=user,
        resource_type="Sale", resource_id=sale.id,
        new_values={"receipt_number": sale.receipt_number, "total": str(sale.total)},
    )

    # Domain event: notification (async-safe)
    _emit_sale_completed(sale)
    return sale


@transaction.atomic
def cancel_sale(*, sale, user=None, reason=""):
    sale = Sale.objects.select_for_update().get(id=sale.id)
    if sale.status == Sale.Status.CANCELLED:
        raise APIError("Sale is already cancelled.",
                       code=ErrorCode.SALE_ALREADY_CANCELLED, status_code=409)
    if sale.status == Sale.Status.REFUNDED:
        raise APIError("Refunded sales cannot be cancelled.",
                       code=ErrorCode.INVALID_STATE_TRANSITION, status_code=409)

    if sale.status == Sale.Status.COMPLETED:
        items = list(sale.items.select_related("product"))
        inventory_services.restore_for_sale(
            business=sale.business, branch=sale.branch, sale=sale,
            items=items, user=user,
        )

    sale.status = Sale.Status.CANCELLED
    sale.save(update_fields=["status", "updated_at"])
    audit_log(
        AuditLog.Action.SALE_CANCELLED,
        business=sale.business, user=user,
        resource_type="Sale", resource_id=sale.id,
        new_values={"reason": reason},
    )
    return sale


@transaction.atomic
def refund_sale(*, sale, user=None, reason=""):
    """Full refund — restore stock, mark sale + payments refunded."""
    sale = Sale.objects.select_for_update().get(id=sale.id)
    if sale.status != Sale.Status.COMPLETED:
        raise APIError("Only completed sales can be refunded.",
                       code=ErrorCode.INVALID_STATE_TRANSITION, status_code=409)

    items = list(sale.items.select_related("product"))
    inventory_services.restore_for_sale(
        business=sale.business, branch=sale.branch, sale=sale,
        items=items, user=user,
    )
    sale.payments.filter(status="completed").update(status="refunded")

    sale.status = Sale.Status.REFUNDED
    sale.payment_status = Sale.PaymentStatus.REFUNDED
    sale.save(update_fields=["status", "payment_status", "updated_at"])
    audit_log(
        AuditLog.Action.SALE_REFUNDED,
        business=sale.business, user=user,
        resource_type="Sale", resource_id=sale.id,
        new_values={"reason": reason},
    )
    return sale


def _emit_sale_completed(sale):
    try:
        from apps.notifications.models import Notification
        from apps.notifications.services import notify_business_members

        notify_business_members(
            sale.business,
            type=Notification.Type.SALE_COMPLETED,
            title=f"Sale {sale.receipt_number} completed",
            message=f"Sale of {sale.total} completed at {sale.branch.name}.",
            data={"sale_id": str(sale.id), "total": str(sale.total)},
            permission="sales.view",
        )
    except Exception:
        logger.exception("Failed to emit sale completed notification")
