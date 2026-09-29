from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.common.models import TenantModel, TimeStampedModel
from apps.common.validators import validate_image_upload


class Category(TenantModel):
    name = models.CharField(max_length=128)
    description = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "name"], name="unique_category_per_business"
            )
        ]
        ordering = ["name"]

    def __str__(self):
        return self.name


class Unit(TenantModel):
    """Units of measure — pieces, kg, litres, boxes…"""

    name = models.CharField(max_length=64)
    abbreviation = models.CharField(max_length=16)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "abbreviation"],
                name="unique_unit_per_business",
            )
        ]
        ordering = ["name"]

    def __str__(self):
        return self.abbreviation


class Product(TenantModel):
    name = models.CharField(max_length=255, db_index=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    sku = models.CharField(max_length=64, blank=True, default="", db_index=True)
    barcode = models.CharField(max_length=64, blank=True, default="", db_index=True)
    description = models.TextField(blank=True, default="")
    buying_price = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    selling_price = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    cost_price = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Moving-average / latest landed cost used for profit calc.",
    )
    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Percent, e.g. 18.00 for 18% VAT",
    )
    track_inventory = models.BooleanField(default=True)
    low_stock_threshold = models.DecimalField(
        max_digits=14, decimal_places=3, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    unit = models.ForeignKey(
        Unit, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="products",
    )
    image = models.ImageField(
        upload_to="products/", null=True, blank=True,
        validators=[validate_image_upload],
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="products_created",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "sku"],
                condition=models.Q(sku__gt=""),
                name="unique_sku_per_business",
            ),
            models.UniqueConstraint(
                fields=["business", "barcode"],
                condition=models.Q(barcode__gt=""),
                name="unique_barcode_per_business",
            ),
        ]
        indexes = [
            models.Index(fields=["business", "is_active", "name"]),
            models.Index(fields=["business", "category"]),
        ]

    def __str__(self):
        return self.name
