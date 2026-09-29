import uuid

from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        LOW_STOCK = "low_stock", "Low Stock"
        SALE_COMPLETED = "sale_completed", "Sale Completed"
        PAYMENT_RECEIVED = "payment_received", "Payment Received"
        INVOICE_OVERDUE = "invoice_overdue", "Invoice Overdue"
        STAFF_INVITATION = "staff_invitation", "Staff Invitation"
        SECURITY = "security", "Security Event"
        SUBSCRIPTION = "subscription", "Subscription Event"
        SYSTEM = "system", "System Announcement"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_index=True,
    )
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
        db_index=True,
    )
    type = models.CharField(max_length=32, choices=Type.choices, db_index=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "read_at", "created_at"]),
            models.Index(fields=["business", "type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.type} → {self.user_id}"
