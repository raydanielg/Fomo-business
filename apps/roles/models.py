from django.db import models

from apps.common.models import TimeStampedModel


class Role(TimeStampedModel):
    """
    A named set of permission strings.

    System roles (business=NULL) are templates. When a business is created,
    roles are materialized per-business so owners can customize them.
    """

    class ReportScope(models.TextChoices):
        OWN = "OWN", "Own records only"
        TEAM = "TEAM", "Team"
        BRANCH = "BRANCH", "Assigned branches"
        ALL_BUSINESS = "ALL_BUSINESS", "Whole business"

    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="roles",
        db_index=True,
    )
    name = models.CharField(max_length=64)
    code = models.CharField(max_length=64, db_index=True)
    description = models.CharField(max_length=255, blank=True, default="")
    permissions = models.JSONField(default=list)
    # Data visibility ceiling for reports. Branch-level membership
    # (allowed_branches) still applies on top of this.
    report_scope = models.CharField(
        max_length=16, choices=ReportScope.choices,
        default=ReportScope.ALL_BUSINESS,
    )
    is_system = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "code"], name="unique_role_code_per_business"
            )
        ]
        ordering = ["code"]

    def __str__(self):
        scope = self.business_id or "system"
        return f"{self.code} ({scope})"

    def grants(self, permission):
        return "*" in self.permissions or permission in self.permissions
