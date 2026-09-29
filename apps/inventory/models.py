from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.common.models import TenantModel, TimeStampedModel


class StockLevel(models.Model):
    """
    Current on-hand quantity per product+branch.

    Derived cache — the source of truth is InventoryMovement; StockLevel is
    updated in the same transaction and can be rebuilt from movements.
    """

    id = models.BigAutoField(primary_key=True)
    business = models.ForeignKey(
        "businesses.Business", on_delete=models.CASCADE,
        related_name="stock_levels", db_index=True,
    )
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.CASCADE,
        related_name="stock_levels", db_index=True,
    )
    product = models.ForeignKey(
        "products.Product", on_delete=models.CASCADE,
        related_name="stock_levels", db_index=True,
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "branch", "product"],
                name="unique_stock_level",
            )
        ]
        indexes = [
            models.Index(fields=["business", "branch", "quantity"]),
        ]

    def __str__(self):
        return f"{self.product_id} @ {self.branch_id}: {self.quantity}"


class InventoryMovement(TenantModel):
    """Immutable stock ledger entry. Never update or delete."""

    class MovementType(models.TextChoices):
        PURCHASE = "PURCHASE", "Purchase"
        SALE = "SALE", "Sale"
        SALE_RETURN = "SALE_RETURN", "Sale Return"
        PURCHASE_RETURN = "PURCHASE_RETURN", "Purchase Return"
        ADJUSTMENT_IN = "ADJUSTMENT_IN", "Adjustment In"
        ADJUSTMENT_OUT = "ADJUSTMENT_OUT", "Adjustment Out"
        TRANSFER_IN = "TRANSFER_IN", "Transfer In"
        TRANSFER_OUT = "TRANSFER_OUT", "Transfer Out"
        DAMAGE = "DAMAGE", "Damage"
        INITIAL_STOCK = "INITIAL_STOCK", "Initial Stock"

    # movements where quantity adds to stock
    INCOMING = {
        MovementType.PURCHASE,
        MovementType.SALE_RETURN,
        MovementType.ADJUSTMENT_IN,
        MovementType.TRANSFER_IN,
        MovementType.INITIAL_STOCK,
    }

    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT,
        related_name="inventory_movements", db_index=True,
    )
    product = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT,
        related_name="inventory_movements", db_index=True,
    )
    movement_type = models.CharField(
        max_length=20, choices=MovementType.choices, db_index=True
    )
    quantity = models.DecimalField(
        max_digits=14, decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
        help_text="Always positive; direction implied by movement_type.",
    )
    unit_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    reference_type = models.CharField(max_length=32, blank=True, default="", db_index=True)
    reference_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    note = models.CharField(max_length=255, blank=True, default="")
    balance_after = models.DecimalField(
        max_digits=14, decimal_places=3, default=Decimal("0"),
        help_text="Stock level after this movement (audit convenience).",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="inventory_movements",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["business", "product", "created_at"]),
            models.Index(fields=["business", "branch", "created_at"]),
            models.Index(fields=["reference_type", "reference_id"]),
        ]

    def __str__(self):
        return f"{self.movement_type} {self.quantity} × {self.product_id}"
