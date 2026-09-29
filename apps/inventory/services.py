"""InventoryService — transaction-safe stock mutations.

Every stock change: locks the StockLevel row (select_for_update), applies the
delta, writes an immutable InventoryMovement with balance_after, all inside a
single atomic block. Negative stock is rejected unless the business opts in.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import F, Q

from apps.common.exceptions import APIError, ErrorCode, InsufficientStockError

from .models import InventoryMovement, StockLevel

ZERO = Decimal("0")


def _lock_stock_level(business, branch, product):
    level, _ = (
        StockLevel.objects.select_for_update()
        .get_or_create(business=business, branch=branch, product=product)
    )
    return level


@transaction.atomic
def apply_movement(*, business, branch, product, movement_type, quantity,
                   unit_cost=ZERO, reference_type="", reference_id="",
                   note="", user=None):
    """
    Apply a single movement. Must be called inside (or wraps) transaction.atomic.
    quantity is always positive — direction comes from movement_type.
    """
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise APIError("Quantity must be positive.", code=ErrorCode.VALIDATION_ERROR)

    incoming = movement_type in InventoryMovement.INCOMING
    level = _lock_stock_level(business, branch, product)

    new_qty = level.quantity + quantity if incoming else level.quantity - quantity
    if new_qty < 0 and not business.allow_negative_stock:
        raise InsufficientStockError(
            f"Insufficient stock for '{product.name}': "
            f"have {level.quantity}, need {quantity}.",
            details={
                "product_id": str(product.id),
                "available": str(level.quantity),
                "requested": str(quantity),
            },
        )

    level.quantity = new_qty
    level.save(update_fields=["quantity", "updated_at"])

    return InventoryMovement.objects.create(
        business=business,
        branch=branch,
        product=product,
        movement_type=movement_type,
        quantity=quantity,
        unit_cost=unit_cost,
        reference_type=reference_type,
        reference_id=str(reference_id or ""),
        note=note,
        balance_after=new_qty,
        created_by=user,
    )


@transaction.atomic
def adjust_stock(*, business, branch, product, quantity, direction, note="", user=None):
    """Manual stock adjustment. direction ∈ {'in', 'out'}."""
    mt = (
        InventoryMovement.MovementType.ADJUSTMENT_IN
        if direction == "in"
        else InventoryMovement.MovementType.ADJUSTMENT_OUT
    )
    movement = apply_movement(
        business=business, branch=branch, product=product,
        movement_type=mt, quantity=quantity, note=note, user=user,
    )
    from apps.audit.models import AuditLog
    from apps.audit.services import log as audit_log

    audit_log(
        AuditLog.Action.STOCK_ADJUSTED,
        business=business, user=user,
        resource_type="Product", resource_id=product.id,
        new_values={"direction": direction, "quantity": str(quantity), "note": note},
    )
    return movement


@transaction.atomic
def transfer_stock(*, business, from_branch, to_branch, product, quantity,
                   note="", user=None):
    """Move stock between branches — two linked movements in one transaction."""
    if from_branch.id == to_branch.id:
        raise APIError("Source and destination branches must differ.",
                       code=ErrorCode.VALIDATION_ERROR)
    out = apply_movement(
        business=business, branch=from_branch, product=product,
        movement_type=InventoryMovement.MovementType.TRANSFER_OUT,
        quantity=quantity, note=note, user=user,
    )
    in_ = apply_movement(
        business=business, branch=to_branch, product=product,
        movement_type=InventoryMovement.MovementType.TRANSFER_IN,
        quantity=quantity, note=note, user=user,
    )
    from apps.audit.models import AuditLog
    from apps.audit.services import log as audit_log

    audit_log(
        AuditLog.Action.STOCK_TRANSFERRED,
        business=business, user=user,
        resource_type="Product", resource_id=product.id,
        new_values={
            "from_branch": str(from_branch.id), "to_branch": str(to_branch.id),
            "quantity": str(quantity),
        },
    )
    return out, in_


def deduct_for_sale(*, business, branch, sale, items, user=None):
    """Deduct stock for a completed sale. Caller must be inside atomic()."""
    movements = []
    for item in items:
        if not item.product.track_inventory:
            continue
        movements.append(
            apply_movement(
                business=business, branch=branch, product=item.product,
                movement_type=InventoryMovement.MovementType.SALE,
                quantity=item.quantity, unit_cost=item.product.cost_price,
                reference_type="Sale", reference_id=sale.id,
                user=user,
            )
        )
    return movements


def restore_for_sale(*, business, branch, sale, items, user=None):
    """Return stock on cancel/refund."""
    movements = []
    for item in items:
        if not item.product.track_inventory:
            continue
        movements.append(
            apply_movement(
                business=business, branch=branch, product=item.product,
                movement_type=InventoryMovement.MovementType.SALE_RETURN,
                quantity=item.quantity, unit_cost=item.product.cost_price,
                reference_type="Sale", reference_id=sale.id,
                user=user,
            )
        )
    return movements


def get_stock(business, product, branch=None):
    qs = StockLevel.objects.filter(business=business, product=product)
    if branch is not None:
        qs = qs.filter(branch=branch)
    return qs.aggregate_total() if hasattr(qs, "aggregate_total") else sum(
        qs.values_list("quantity", flat=True)
    )


def low_stock_products(*, business_id=None):
    """Products whose stock at any branch is at/below threshold."""
    return (
        StockLevel.objects.filter(
            product__track_inventory=True,
            product__is_active=True,
            product__low_stock_threshold__gt=0,
        )
        .filter(Q(business_id=business_id) if business_id else Q())
        .filter(quantity__lte=F("product__low_stock_threshold"))
        .select_related("product", "branch", "business")
    )
