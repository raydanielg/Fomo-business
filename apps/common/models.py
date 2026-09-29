import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base: UUID pk + created/updated timestamps."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantModel(TimeStampedModel):
    """Abstract base for models owned by a Business (tenant)."""

    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="%(class)s_set",
        db_index=True,
    )

    class Meta:
        abstract = True
