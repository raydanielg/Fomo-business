from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel


class Plan(TimeStampedModel):
    """Subscription plan definition. Limits/features are data, not code."""

    class BillingInterval(models.TextChoices):
        MONTHLY = "MONTHLY", "Monthly"
        YEARLY = "YEARLY", "Yearly"
        CUSTOM = "CUSTOM", "Custom"

    code = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=64)
    description = models.TextField(blank=True, default="")
    price_monthly = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    price_yearly = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default=settings.DEFAULT_CURRENCY)
    billing_interval = models.CharField(
        max_length=16, choices=BillingInterval.choices,
        default=BillingInterval.MONTHLY,
    )
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(
        default=True, help_text="Shown on the public plan-comparison page."
    )
    sort_order = models.PositiveIntegerField(default=0)

    # limits: {"max_products": 100, "max_staff": 2, "max_branches": 1,
    #          "max_monthly_sales": 500, "max_sms": 50}
    # None / missing key = unlimited
    limits = models.JSONField(default=dict, blank=True)
    # features: {"advanced_reports": true, "multi_branch": false, ...}
    features = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["sort_order", "price_monthly"]

    def __str__(self):
        return self.name

    def limit(self, key):
        return self.limits.get(key)

    def has_feature(self, key):
        """
        Source of truth is PlanFeature rows; the legacy `features` JSON dict is
        a fallback for plans not yet migrated to the Feature catalog.
        """
        pf = self.plan_features.filter(feature__key=key).first()
        if pf is not None:
            return pf.enabled and pf.feature.is_active
        return bool(self.features.get(key, False))

    def feature_configuration(self, key):
        pf = self.plan_features.filter(feature__key=key).first()
        return pf.configuration if pf is not None else {}


class Feature(TimeStampedModel):
    """A capability that can be entitled to a plan (reports.export, …)."""

    class Category(models.TextChoices):
        SALES = "SALES", "Sales"
        INVENTORY = "INVENTORY", "Inventory"
        CUSTOMERS = "CUSTOMERS", "Customers"
        FINANCE = "FINANCE", "Finance"
        REPORTS = "REPORTS", "Reports"
        STAFF = "STAFF", "Staff"
        BRANCHES = "BRANCHES", "Branches"
        NOTIFICATIONS = "NOTIFICATIONS", "Notifications"
        EXPORTS = "EXPORTS", "Exports"
        ANALYTICS = "ANALYTICS", "Analytics"
        INTEGRATIONS = "INTEGRATIONS", "Integrations"

    class FeatureType(models.TextChoices):
        BOOLEAN = "BOOLEAN", "Boolean"
        LIMIT = "LIMIT", "Limit"
        CONFIGURED = "CONFIGURED", "Configured"

    key = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True, default="")
    category = models.CharField(
        max_length=32, choices=Category.choices, default=Category.REPORTS
    )
    feature_type = models.CharField(
        max_length=16, choices=FeatureType.choices, default=FeatureType.BOOLEAN
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "key"]

    def __str__(self):
        return self.key


class PlanFeature(TimeStampedModel):
    """Entitles a Feature to a Plan, optionally with JSON configuration
    (limits, allowed capabilities, export formats, …)."""

    plan = models.ForeignKey(
        Plan, on_delete=models.CASCADE, related_name="plan_features", db_index=True
    )
    feature = models.ForeignKey(
        Feature, on_delete=models.CASCADE, related_name="plan_features", db_index=True
    )
    enabled = models.BooleanField(default=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "feature"], name="unique_plan_feature"
            )
        ]

    def __str__(self):
        return f"{self.plan.code}:{self.feature.key}={'on' if self.enabled else 'off'}"


class Subscription(TimeStampedModel):
    class Status(models.TextChoices):
        TRIALING = "trialing", "Trialing"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past Due"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    class Interval(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    business = models.OneToOneField(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    interval = models.CharField(
        max_length=16, choices=Interval.choices, default=Interval.MONTHLY
    )
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "current_period_end"])]

    def __str__(self):
        return f"{self.business.name} → {self.plan.code} ({self.status})"

    @property
    def is_active(self):
        if self.status not in (self.Status.ACTIVE, self.Status.TRIALING):
            return False
        if self.current_period_end and self.current_period_end < timezone.now():
            return False
        return True


class SubscriptionEvent(TimeStampedModel):
    """Lifecycle history of a subscription (audit)."""

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="events"
    )
    event_type = models.CharField(max_length=64, db_index=True)
    old_plan = models.CharField(max_length=32, blank=True, default="")
    new_plan = models.CharField(max_length=32, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)


class UsageRecord(models.Model):
    """Per-period usage counters powering entitlement checks and billing."""

    class Metric(models.TextChoices):
        SALES_COUNT = "sales_count", "Sales Count"
        PRODUCTS_COUNT = "products_count", "Products Count"
        STAFF_COUNT = "staff_count", "Staff Count"
        BRANCHES_COUNT = "branches_count", "Branches Count"
        SMS_COUNT = "sms_count", "SMS Count"
        WHATSAPP_COUNT = "whatsapp_count", "WhatsApp Count"
        INVOICES_COUNT = "invoices_count", "Invoices Count"
        REPORT_EXPORTS = "report_exports", "Report Exports"

    id = models.BigAutoField(primary_key=True)
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="usage_records",
        db_index=True,
    )
    metric = models.CharField(max_length=32, choices=Metric.choices)
    period = models.DateField(help_text="First day of the usage period (monthly).")
    value = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "metric", "period"],
                name="unique_usage_per_period",
            )
        ]
        indexes = [models.Index(fields=["business", "metric", "period"])]
