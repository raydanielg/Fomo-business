from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.common.models import TenantModel


class Purchase(TenantModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT,
        related_name="purchases", db_index=True,
    )
    supplier = models.ForeignKey(
        "suppliers.Supplier", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="purchases",
    )
    reference = models.CharField(max_length=64, blank=True, default="", db_index=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    received_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="purchases_created",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["business", "status", "created_at"]),
            models.Index(fields=["business", "supplier"]),
        ]


class PurchaseItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    purchase = models.ForeignKey(
        Purchase, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT, related_name="purchase_items"
    )
    quantity = models.DecimalField(
        max_digits=14, decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    unit_cost = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))

    class Meta:
        indexes = [models.Index(fields=["purchase"]), models.Index(fields=["product"])]
