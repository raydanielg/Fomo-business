from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel


class Membership(TimeStampedModel):
    """Links a User to a Business with a Role — the tenancy boundary."""

    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        REMOVED = "removed", "Removed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
        db_index=True,
    )
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="memberships",
        db_index=True,
    )
    role = models.ForeignKey(
        "roles.Role",
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.INVITED, db_index=True
    )
    joined_at = models.DateTimeField(null=True, blank=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitations_sent",
    )
    # Empty → access to all branches; otherwise restricted to this set
    allowed_branches = models.ManyToManyField(
        "branches.Branch", blank=True, related_name="memberships"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "business"], name="unique_membership"
            )
        ]
        indexes = [
            models.Index(fields=["business", "status"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"{self.user_id} @ {self.business_id} ({self.role.code})"

    # -- helpers -------------------------------------------------------------

    @property
    def is_owner(self):
        return self.role.code == "OWNER"

    def get_permissions(self):
        return set(self.role.permissions or [])

    def has_permission(self, permission):
        return self.role.grants(permission)

    def has_any_permission(self, *permissions):
        perms = self.get_permissions()
        if "*" in perms:
            return True
        return any(p in perms for p in permissions)

    def can_access_branch(self, branch_id):
        """Empty allowed_branches means all branches."""
        if not self.allowed_branches.exists():
            return True
        return self.allowed_branches.filter(id=branch_id).exists()

    def activate(self):
        self.status = self.Status.ACTIVE
        self.joined_at = timezone.now()
        self.save(update_fields=["status", "joined_at"])
