from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.models import TenantModel


class ExpenseCategory(TenantModel):
    name = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "name"],
                name="unique_expense_category_per_business",
            )
        ]
        ordering = ["name"]

    def __str__(self):
        return self.name


class Expense(TenantModel):
    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile Money"
        BANK = "BANK", "Bank"
        CARD = "CARD", "Card"
        OTHER = "OTHER", "Other"

    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT,
        related_name="expenses", db_index=True, null=True, blank=True,
    )
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT, related_name="expenses"
    )
    amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    payment_method = models.CharField(
        max_length=16, choices=Method.choices, default=Method.CASH
    )
    description = models.TextField(blank=True, default="")
    reference = models.CharField(max_length=128, blank=True, default="")
    expense_date = models.DateField(default=timezone.localdate, db_index=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="expenses_created",
    )

    class Meta:
        ordering = ["-expense_date", "-created_at"]
        indexes = [
            models.Index(fields=["business", "expense_date"]),
            models.Index(fields=["business", "category", "expense_date"]),
        ]

    def __str__(self):
        return f"{self.amount} — {self.category_id}"
