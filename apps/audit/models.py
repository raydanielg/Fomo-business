import uuid

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Immutable record of significant actions. Never update or delete."""

    class Action(models.TextChoices):
        LOGIN = "auth.login", "Login"
        LOGIN_FAILED = "auth.login_failed", "Login Failed"
        LOGOUT = "auth.logout", "Logout"
        PASSWORD_CHANGE = "auth.password_change", "Password Change"
        PASSWORD_RESET = "auth.password_reset", "Password Reset"
        STAFF_INVITED = "staff.invited", "Staff Invited"
        STAFF_REMOVED = "staff.removed", "Staff Removed"
        STAFF_UPDATED = "staff.updated", "Staff Updated"
        ROLE_CHANGED = "staff.role_changed", "Role Changed"
        PRODUCT_CREATED = "product.created", "Product Created"
        PRODUCT_UPDATED = "product.updated", "Product Updated"
        PRODUCT_DELETED = "product.deleted", "Product Deleted"
        STOCK_ADJUSTED = "inventory.adjusted", "Stock Adjusted"
        STOCK_TRANSFERRED = "inventory.transferred", "Stock Transferred"
        SALE_CREATED = "sale.created", "Sale Created"
        SALE_COMPLETED = "sale.completed", "Sale Completed"
        SALE_CANCELLED = "sale.cancelled", "Sale Cancelled"
        SALE_REFUNDED = "sale.refunded", "Sale Refunded"
        PAYMENT_RECEIVED = "payment.received", "Payment Received"
        EXPENSE_CREATED = "expense.created", "Expense Created"
        EXPENSE_UPDATED = "expense.updated", "Expense Updated"
        EXPENSE_DELETED = "expense.deleted", "Expense Deleted"
        INVOICE_CREATED = "invoice.created", "Invoice Created"
        INVOICE_UPDATED = "invoice.updated", "Invoice Updated"
        INVOICE_CANCELLED = "invoice.cancelled", "Invoice Cancelled"
        CUSTOMER_CREATED = "customer.created", "Customer Created"
        CUSTOMER_UPDATED = "customer.updated", "Customer Updated"
        SUPPLIER_CREATED = "supplier.created", "Supplier Created"
        SUPPLIER_UPDATED = "supplier.updated", "Supplier Updated"
        BUSINESS_UPDATED = "business.updated", "Business Updated"
        SUBSCRIPTION_CHANGED = "subscription.changed", "Subscription Changed"
        MEMBERSHIP_CREATED = "membership.created", "Membership Created"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="audit_logs",
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=64, choices=Action.choices, db_index=True)
    resource_type = models.CharField(max_length=64, db_index=True)
    resource_id = models.CharField(max_length=64, blank=True, default="")
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default="")
    request_id = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["business", "action", "created_at"]),
            models.Index(fields=["resource_type", "resource_id"]),
        ]

    def __str__(self):
        return f"{self.action} by {self.user_id} at {self.created_at}"
