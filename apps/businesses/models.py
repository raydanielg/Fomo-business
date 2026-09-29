from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.common.models import TimeStampedModel
from apps.common.validators import validate_image_upload


class Business(TimeStampedModel):
    """A tenant. All operational data hangs off a Business."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        CLOSED = "closed", "Closed"

    class Type(models.TextChoices):
        RETAIL = "retail", "Retail"
        GROCERY = "grocery", "Grocery"
        RESTAURANT = "restaurant", "Restaurant"
        HARDWARE = "hardware", "Hardware"
        CLOTHING = "clothing", "Clothing"
        ELECTRONICS = "electronics", "Electronics"
        PHARMACY = "pharmacy", "Pharmacy"
        COSMETICS = "cosmetics", "Cosmetics"
        SALON = "salon", "Salon"
        WHOLESALE = "wholesale", "Wholesale"
        SERVICE = "service", "Service"
        OTHER = "other", "Other"

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, db_index=True)
    business_type = models.CharField(
        max_length=32, choices=Type.choices, default=Type.OTHER
    )
    registration_number = models.CharField(max_length=64, blank=True, default="")
    tax_number = models.CharField(max_length=64, blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="", db_index=True)
    email = models.EmailField(blank=True, default="", db_index=True)
    address = models.TextField(blank=True, default="")
    city = models.CharField(max_length=128, blank=True, default="")
    region = models.CharField(max_length=128, blank=True, default="")
    country = models.CharField(max_length=64, default=settings.DEFAULT_COUNTRY)
    currency = models.CharField(max_length=3, default=settings.DEFAULT_CURRENCY)
    timezone = models.CharField(max_length=64, default=settings.DEFAULT_TIMEZONE)
    logo = models.ImageField(
        upload_to="businesses/logos/",
        null=True,
        blank=True,
        validators=[validate_image_upload],
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_businesses",
    )
    # Behaviour flags
    allow_negative_stock = models.BooleanField(default=False)
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:240] or "business"
            slug = base
            counter = 1
            while Business.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f"{base}-{counter}"
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
