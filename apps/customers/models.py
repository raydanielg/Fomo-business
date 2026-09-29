from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.common.models import TenantModel


class Customer(TenantModel):
    name = models.CharField(max_length=255, db_index=True)
    phone = models.CharField(max_length=32, blank=True, default="", db_index=True)
    email = models.EmailField(blank=True, default="", db_index=True)
    address = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    credit_limit = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    current_balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        help_text="Outstanding balance owed by the customer.",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="customers_created",
    )

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["business", "is_active", "name"]),
            models.Index(fields=["business", "phone"]),
        ]

    def __str__(self):
        return self.name
