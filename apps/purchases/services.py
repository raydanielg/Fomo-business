"""PurchaseService — receiving stock from suppliers."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import APIError, ErrorCode
from apps.inventory import services as inventory_services
from apps.inventory.models import InventoryMovement
from apps.products.models import Product

from .models import Purchase, PurchaseItem

ZERO = Decimal("0")
CENT = Decimal("0.01")


def _money(v):
    return Decimal(str(v)).quantize(CENT)


@transaction.atomic
def create_purchase(*, business, branch, user, items_data, supplier=None,
                    reference="", notes="", receive_immediately=True):
    if not items_data:
        raise APIError("A purchase requires at least one item.",
                       code=ErrorCode.VALIDATION_ERROR)

    items = []
    subtotal = ZERO
    for entry in items_data:
        product = Product.objects.filter(
            business=business, id=entry["product_id"]
        ).first()
        if product is None:
            raise APIError(f"Product {entry['product_id']} not found.",
                           code=ErrorCode.PRODUCT_NOT_FOUND, status_code=404)
        quantity = Decimal(str(entry["quantity"]))
        unit_cost = _money(entry["unit_cost"])
        line_total = _money(quantity * unit_cost)
        items.append({"product": product, "quantity": quantity,
                      "unit_cost": unit_cost, "total": line_total})
        subtotal += line_total

    purchase = Purchase.objects.create(
        business=business, branch=branch, supplier=supplier,
        reference=reference, subtotal=subtotal, total=subtotal,
        status=Purchase.Status.DRAFT, notes=notes, created_by=user,
    )
    PurchaseItem.objects.bulk_create(
        PurchaseItem(purchase=purchase, **i) for i in items
    )

    if receive_immediately:
        receive_purchase(purchase=purchase, user=user)
    return purchase


@transaction.atomic
def receive_purchase(*, purchase, user=None):
    purchase = Purchase.objects.select_for_update().get(id=purchase.id)
    if purchase.status == Purchase.Status.RECEIVED:
        raise APIError("Purchase already received.",
                       code=ErrorCode.INVALID_STATE_TRANSITION, status_code=409)
    if purchase.status == Purchase.Status.CANCELLED:
        raise APIError("Cancelled purchases cannot be received.",
                       code=ErrorCode.INVALID_STATE_TRANSITION, status_code=409)

    for item in purchase.items.select_related("product"):
        if not item.product.track_inventory:
            continue
        inventory_services.apply_movement(
            business=purchase.business, branch=purchase.branch,
            product=item.product,
            movement_type=InventoryMovement.MovementType.PURCHASE,
            quantity=item.quantity, unit_cost=item.unit_cost,
            reference_type="Purchase", reference_id=purchase.id, user=user,
        )
        # update landed cost
        item.product.cost_price = item.unit_cost
        item.product.save(update_fields=["cost_price", "updated_at"])

    purchase.status = Purchase.Status.RECEIVED
    purchase.received_at = timezone.now()
    purchase.save(update_fields=["status", "received_at", "updated_at"])

    if purchase.supplier:
        supplier = purchase.supplier.__class__.objects.select_for_update().get(
            id=purchase.supplier.id
        )
        supplier.balance += purchase.total
        supplier.save(update_fields=["balance", "updated_at"])
    return purchase


@transaction.atomic
def cancel_purchase(*, purchase, user=None):
    purchase = Purchase.objects.select_for_update().get(id=purchase.id)
    if purchase.status == Purchase.Status.RECEIVED:
        # reverse stock
        for item in purchase.items.select_related("product"):
            if not item.product.track_inventory:
                continue
            inventory_services.apply_movement(
                business=purchase.business, branch=purchase.branch,
                product=item.product,
                movement_type=InventoryMovement.MovementType.PURCHASE_RETURN,
                quantity=item.quantity, unit_cost=item.unit_cost,
                reference_type="Purchase", reference_id=purchase.id, user=user,
            )
        if purchase.supplier:
            supplier = purchase.supplier.__class__.objects.select_for_update().get(
                id=purchase.supplier.id
            )
            supplier.balance -= purchase.total
            if supplier.balance < 0:
                supplier.balance = Decimal("0")
            supplier.save(update_fields=["balance", "updated_at"])
    purchase.status = Purchase.Status.CANCELLED
    purchase.save(update_fields=["status", "updated_at"])
    return purchase
