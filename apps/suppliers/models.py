from decimal import Decimal

from django.db import models

from apps.common.models import TenantModel


class Supplier(TenantModel):
    name = models.CharField(max_length=255, db_index=True)
    phone = models.CharField(max_length=32, blank=True, default="", db_index=True)
    email = models.EmailField(blank=True, default="", db_index=True)
    address = models.TextField(blank=True, default="")
    tax_number = models.CharField(max_length=64, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        help_text="Amount owed to the supplier.",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="suppliers_created",
    )

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["business", "is_active", "name"])]

    def __str__(self):
        return self.name
