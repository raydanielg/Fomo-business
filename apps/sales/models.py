from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.common.models import TenantModel


class Sale(TenantModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PARTIAL = "partial", "Partial"
        PAID = "paid", "Paid"
        REFUNDED = "refunded", "Refunded"

    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT,
        related_name="sales", db_index=True,
    )
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="sales",
    )
    invoice = models.OneToOneField(
        "invoices.Invoice", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="sale",
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="sales",
    )
    receipt_number = models.CharField(max_length=32, db_index=True, blank=True, default="")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    discount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    amount_paid = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    balance_due = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    payment_status = models.CharField(
        max_length=16, choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID, db_index=True,
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "receipt_number"],
                condition=models.Q(receipt_number__gt=""),
                name="unique_receipt_number_per_business",
            )
        ]
        indexes = [
            models.Index(fields=["business", "status", "created_at"]),
            models.Index(fields=["business", "branch", "created_at"]),
            models.Index(fields=["business", "customer", "created_at"]),
            models.Index(fields=["business", "payment_status"]),
        ]

    def __str__(self):
        return f"Sale {self.receipt_number or self.id}"


class SaleItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT, related_name="sale_items"
    )
    quantity = models.DecimalField(
        max_digits=14, decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    unit_price = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    discount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))

    class Meta:
        indexes = [models.Index(fields=["sale"]), models.Index(fields=["product"])]
