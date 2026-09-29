import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import TenantModel, TimeStampedModel


class Report(TimeStampedModel):
    """Central catalog of available reports — configured in admin, not code."""

    class Category(models.TextChoices):
        SALES = "sales", "Sales"
        INVENTORY = "inventory", "Inventory"
        EXPENSES = "expenses", "Expenses"
        CUSTOMERS = "customers", "Customers"
        SUPPLIERS = "suppliers", "Suppliers"
        PROFIT = "profit", "Profit"
        PAYMENTS = "payments", "Payments"
        STAFF = "staff", "Staff"
        BRANCHES = "branches", "Branches"
        TAX = "tax", "Tax"
        ADVANCED = "advanced", "Advanced Analytics"

    class Capability(models.TextChoices):
        VIEW = "view", "View"
        FILTER = "filter", "Filter"
        EXPORT = "export", "Export"
        PRINT = "print", "Print"
        SCHEDULE = "schedule", "Schedule"
        SHARE = "share", "Share"
        COMPARE = "compare", "Compare"
        ADVANCED_FILTERS = "advanced_filters", "Advanced Filters"

    class MinAccess(models.TextChoices):
        ANY = "any", "Any member"
        MANAGER = "manager", "Manager+"
        OWNER = "owner", "Owner only"

    key = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True, default="")
    category = models.CharField(max_length=32, choices=Category.choices)
    # the Feature key a plan must include for this report to be accessible
    feature_key = models.CharField(max_length=64, db_index=True)
    # capabilities the report itself supports (plan narrows further)
    capabilities = models.JSONField(default=list)
    # filters the report supports (plan narrows further)
    supported_filters = models.JSONField(default=list)
    minimum_access_level = models.CharField(
        max_length=16, choices=MinAccess.choices, default=MinAccess.ANY
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["category", "sort_order", "key"]

    def __str__(self):
        return self.key

    @property
    def permission_key(self):
        """Role permission needed to view this report category."""
        return f"reports.{self.category}"


class ScheduledReport(TenantModel):
    """A report configured to run on a schedule and be emailed to recipients."""

    class Frequency(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    class Format(models.TextChoices):
        CSV = "csv", "CSV"
        XLSX = "xlsx", "Excel"
        PDF = "pdf", "PDF"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        DISABLED = "disabled", "Disabled"

    report = models.ForeignKey(
        Report, on_delete=models.CASCADE, related_name="schedules"
    )
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="scheduled_reports",
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="scheduled_reports",
    )
    recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="report_subscriptions"
    )
    frequency = models.CharField(max_length=16, choices=Frequency.choices)
    day_of_week = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="0=Monday … 6=Sunday (weekly)"
    )
    day_of_month = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="1-28 (monthly)"
    )
    hour = models.PositiveSmallIntegerField(default=8)
    format = models.CharField(
        max_length=8, choices=Format.choices, default=Format.CSV
    )
    filters = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    next_run_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_run_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["next_run_at"]

    def compute_next_run(self, from_dt=None):
        from_dt = from_dt or timezone.now()
        base = from_dt.replace(minute=0, second=0, microsecond=0)
        candidate = base.replace(hour=min(self.hour, 23))
        if candidate <= from_dt:
            candidate = base + timedelta(days=1)
            candidate = candidate.replace(hour=min(self.hour, 23))

        if self.frequency == self.Frequency.DAILY:
            return candidate
        if self.frequency == self.Frequency.WEEKLY:
            dow = self.day_of_week if self.day_of_week is not None else 0
            days_ahead = (dow - candidate.weekday()) % 7
            if days_ahead == 0 and candidate <= from_dt:
                days_ahead = 7
            return candidate + timedelta(days=days_ahead)
        # monthly
        dom = min(self.day_of_month or 1, 28)
        year, month = candidate.year, candidate.month
        if candidate.day > dom or (candidate.day == dom and candidate <= from_dt):
            month += 1
            if month > 12:
                month, year = 1, year + 1
        return candidate.replace(year=year, month=month, day=dom)


class ReportUsage(models.Model):
    """Per-business report usage for analytics (never cross-tenant)."""

    class Action(models.TextChoices):
        VIEW = "view", "Viewed"
        EXPORT = "export", "Exported"
        SCHEDULE = "schedule", "Scheduled"
        DENIED = "denied", "Access Denied"

    id = models.BigAutoField(primary_key=True)
    business = models.ForeignKey(
        "businesses.Business", on_delete=models.CASCADE,
        related_name="report_usage", db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="report_usage",
    )
    report_key = models.CharField(max_length=64, db_index=True)
    action = models.CharField(max_length=16, choices=Action.choices, db_index=True)
    format = models.CharField(max_length=8, blank=True, default="")
    row_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["business", "report_key", "action"]),
            models.Index(fields=["business", "action", "created_at"]),
        ]


class EntitlementEvent(models.Model):
    """Audit trail of entitlement decisions — denials + plan changes."""

    class EventType(models.TextChoices):
        ACCESS_DENIED = "access_denied", "Access Denied"
        EXPORT_DENIED = "export_denied", "Export Denied"
        FEATURE_DENIED = "feature_denied", "Feature Denied"
        LIMIT_REACHED = "limit_reached", "Limit Reached"
        PLAN_CHANGED = "plan_changed", "Plan Changed"
        UPGRADED = "upgraded", "Upgraded"
        DOWNGRADED = "downgraded", "Downgraded"

    id = models.BigAutoField(primary_key=True)
    business = models.ForeignKey(
        "businesses.Business", on_delete=models.CASCADE,
        related_name="entitlement_events", db_index=True,
        null=True, blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="entitlement_events",
    )
    event_type = models.CharField(max_length=32, choices=EventType.choices, db_index=True)
    feature_key = models.CharField(max_length=64, blank=True, default="")
    report_key = models.CharField(max_length=64, blank=True, default="")
    reason = models.CharField(max_length=64, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["business", "event_type", "created_at"]),
        ]
