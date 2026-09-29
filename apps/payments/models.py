from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.models import TenantModel


class Payment(TenantModel):
    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile Money"
        BANK = "BANK", "Bank"
        CARD = "CARD", "Card"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT,
        related_name="payments", db_index=True, null=True, blank=True,
    )
    sale = models.ForeignKey(
        "sales.Sale", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="payments",
    )
    invoice = models.ForeignKey(
        "invoices.Invoice", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="payments",
    )
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="payments",
    )
    amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    method = models.CharField(max_length=16, choices=Method.choices, db_index=True)
    reference = models.CharField(max_length=128, blank=True, default="", db_index=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.COMPLETED, db_index=True
    )
    paid_at = models.DateTimeField(default=timezone.now, db_index=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="payments_received",
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-paid_at"]
        indexes = [
            models.Index(fields=["business", "method", "paid_at"]),
            models.Index(fields=["business", "status", "paid_at"]),
            models.Index(fields=["sale"]),
            models.Index(fields=["invoice"]),
        ]

    def __str__(self):
        return f"Payment {self.amount} {self.method}"
