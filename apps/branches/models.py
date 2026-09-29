from django.conf import settings
from django.db import models

from apps.common.models import TenantModel


class Branch(TenantModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=32, db_index=True)
    phone = models.CharField(max_length=32, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    address = models.TextField(blank=True, default="")
    city = models.CharField(max_length=128, blank=True, default="")
    region = models.CharField(max_length=128, blank=True, default="")
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_branches",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "code"], name="unique_branch_code_per_business"
            )
        ]
        ordering = ["name"]
        indexes = [models.Index(fields=["business", "is_active"])]

    def __str__(self):
        return f"{self.business.name} / {self.name}"
