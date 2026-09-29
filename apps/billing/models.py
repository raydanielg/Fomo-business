"""Billing models — normalized, provider-agnostic records that mirror
provider objects (Snippe today) into Fomo's canonical payment model.

The frontend never consumes provider payloads directly; these models are
the single source of truth for the Billing & Payments admin surface.
"""

import uuid

from django.db import models


class PaymentProvider(models.Model):
    """A configured payment provider (Snippe first, more later)."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DISABLED = "disabled", "Disabled"
        ERROR = "error", "Error"

    class Environment(models.TextChoices):
        SANDBOX = "sandbox", "Sandbox"
        PRODUCTION = "production", "Production"

    code = models.CharField(max_length=32, unique=True)  # "snippe"
    name = models.CharField(max_length=64)
    api_version = models.CharField(max_length=32, default="")
    environment = models.CharField(
        max_length=16, choices=Environment.choices, default=Environment.SANDBOX
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE
    )
    is_primary = models.BooleanField(default=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.code} ({self.environment})"


class NormalizedStatus(models.TextChoices):
    """Fomo's canonical payment status — provider statuses map onto this."""

    PENDING = "pending", "Pending"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    VOIDED = "voided", "Voided"
    EXPIRED = "expired", "Expired"
    CANCELLED = "cancelled", "Cancelled"
    REFUNDED = "refunded", "Refunded"


class ProviderPayment(models.Model):
    """A payment processed through a provider (Snippe).

    Distinct from apps.payments.Payment (tenant-side cash/card records) —
    this is the platform-level provider record the Billing console shows.
    """

    class Channel(models.TextChoices):
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        CARD = "card", "Card"
        BANK = "bank", "Bank"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "businesses.Business", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="provider_payments",
        db_index=True,
    )
    provider = models.ForeignKey(
        PaymentProvider, on_delete=models.PROTECT,
        related_name="payments",
    )
    reference = models.CharField(max_length=64, unique=True, db_index=True)
    external_reference = models.CharField(
        max_length=128, blank=True, default="", db_index=True
    )
    channel = models.CharField(
        max_length=16, choices=Channel.choices, default=Channel.MOBILE_MONEY
    )
    channel_detail = models.CharField(
        max_length=32, blank=True, default="",
        help_text="Provider-reported method, e.g. mpesa, airtel_money.",
    )
    customer_name = models.CharField(max_length=255, blank=True, default="")
    customer_phone = models.CharField(max_length=32, blank=True, default="")
    customer_email = models.EmailField(blank=True, default="")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    fee = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0
    )
    currency = models.CharField(max_length=8, default="TZS")
    status = models.CharField(
        max_length=16, choices=NormalizedStatus.choices,
        default=NormalizedStatus.PENDING, db_index=True,
    )
    status_reason = models.TextField(
        blank=True, default="",
        help_text="Normalized failure/void/expiry reason from provider.",
    )
    idempotency_key = models.CharField(max_length=80, unique=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["provider", "status", "created_at"]),
            models.Index(fields=["business", "status"]),
        ]

    def __str__(self):
        return f"{self.reference} {self.amount} {self.status}"


class CheckoutSession(models.Model):
    """Provider checkout session (Snippe Sessions)."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        COMPLETED = "completed", "Completed"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "businesses.Business", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="checkout_sessions",
    )
    provider = models.ForeignKey(
        PaymentProvider, on_delete=models.PROTECT,
        related_name="checkout_sessions",
    )
    session_reference = models.CharField(max_length=64, unique=True)
    checkout_url = models.URLField(blank=True, default="")
    payment_link_url = models.URLField(blank=True, default="")
    customer_name = models.CharField(max_length=255, blank=True, default="")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=8, default="TZS")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.OPEN,
        db_index=True,
    )
    payment = models.ForeignKey(
        ProviderPayment, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="checkout_sessions",
    )
    opened_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class PaymentLink(models.Model):
    """Shareable payment link backed by a provider session."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DISABLED = "disabled", "Disabled"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "businesses.Business", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="payment_links",
    )
    provider = models.ForeignKey(
        PaymentProvider, on_delete=models.PROTECT,
        related_name="payment_links",
    )
    reference = models.CharField(max_length=64, unique=True, db_index=True)
    url = models.URLField()
    description = models.CharField(max_length=255, blank=True, default="")
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Null means custom/payer-entered amount.",
    )
    currency = models.CharField(max_length=8, default="TZS")
    custom_amount = models.BooleanField(default=False)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE
    )
    payments_count = models.PositiveIntegerField(default=0)
    total_collected = models.DecimalField(
        max_digits=14, decimal_places=2, default=0
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Refund(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(
        ProviderPayment, on_delete=models.PROTECT, related_name="refunds"
    )
    provider = models.ForeignKey(
        PaymentProvider, on_delete=models.PROTECT, related_name="refunds"
    )
    reference = models.CharField(max_length=64, unique=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=8, default="TZS")
    reason = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="refunds_created",
    )

    class Meta:
        ordering = ["-created_at"]


class Payout(models.Model):
    """Money sent out via a provider disbursement (when supported)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REVERSED = "reversed", "Reversed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "businesses.Business", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="payouts",
    )
    provider = models.ForeignKey(
        PaymentProvider, on_delete=models.PROTECT, related_name="payouts"
    )
    reference = models.CharField(max_length=64, unique=True, db_index=True)
    external_reference = models.CharField(max_length=128, blank=True, default="")
    recipient_name = models.CharField(max_length=255, blank=True, default="")
    recipient_phone = models.CharField(max_length=32, blank=True, default="")
    channel = models.CharField(max_length=32, blank=True, default="")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    fee = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=8, default="TZS")
    narration = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING,
        db_index=True,
    )
    status_reason = models.TextField(blank=True, default="")
    idempotency_key = models.CharField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class WebhookEvent(models.Model):
    """A provider webhook delivery — raw receipt + normalized processing
    state. Signature is verified on the raw request body before storage."""

    class SignatureStatus(models.TextChoices):
        VERIFIED = "verified", "Signature Verified"
        INVALID = "invalid", "Signature Invalid"
        REPLAY_REJECTED = "replay_rejected", "Replay Rejected"

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Processing Failed"
        DUPLICATE = "duplicate", "Duplicate Event"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(
        PaymentProvider, on_delete=models.PROTECT, related_name="webhooks"
    )
    event_id = models.CharField(max_length=128, db_index=True)
    event_type = models.CharField(max_length=64, db_index=True)
    signature_status = models.CharField(
        max_length=24, choices=SignatureStatus.choices
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.RECEIVED,
        db_index=True,
    )
    payment_reference = models.CharField(max_length=128, blank=True, default="")
    attempts = models.PositiveIntegerField(default=0)
    processing_ms = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "event_id"],
                name="unique_webhook_event_per_provider",
            )
        ]


class PaymentEvent(models.Model):
    """Normalized internal event — one row per state change of a payment.
    The payment timeline and live-activity feed read from this."""

    class Type(models.TextChoices):
        CREATED = "payment.created", "Payment Created"
        INITIATED = "payment.initiated", "Payment Initiated"
        PENDING = "payment.pending", "Payment Pending"
        COMPLETED = "payment.completed", "Payment Completed"
        FAILED = "payment.failed", "Payment Failed"
        EXPIRED = "payment.expired", "Payment Expired"
        VOIDED = "payment.voided", "Payment Voided"
        REFUND_INITIATED = "refund.initiated", "Refund Initiated"
        REFUND_COMPLETED = "refund.completed", "Refund Completed"
        PAYOUT_INITIATED = "payout.initiated", "Payout Initiated"
        PAYOUT_COMPLETED = "payout.completed", "Payout Completed"
        PAYOUT_FAILED = "payout.failed", "Payout Failed"
        PAYOUT_REVERSED = "payout.reversed", "Payout Reversed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(
        ProviderPayment, on_delete=models.CASCADE,
        related_name="events", null=True, blank=True,
    )
    event_type = models.CharField(max_length=32, choices=Type.choices)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=8, default="TZS")
    status = models.CharField(max_length=16, blank=True, default="")
    source = models.CharField(
        max_length=16, default="webhook",
        help_text="webhook | api | admin",
    )
    webhook_event = models.ForeignKey(
        WebhookEvent, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payment_events",
    )
    detail = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["payment", "created_at"])]


class ReconciliationStatus(models.TextChoices):
    MATCHED = "matched", "Matched"
    MISMATCH = "mismatch", "Mismatch"
    MISSING_PROVIDER_RECORD = "missing_provider", "Missing Provider Record"
    MISSING_INTERNAL_RECORD = "missing_internal", "Missing Internal Record"
    PENDING = "pending", "Pending"
    MANUAL_REVIEW = "manual_review", "Manual Review"


class ReconciliationRecord(models.Model):
    """One reconciliation check: Fomo payment vs provider record."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(
        ProviderPayment, on_delete=models.CASCADE,
        related_name="reconciliation", null=True, blank=True,
    )
    provider = models.ForeignKey(
        PaymentProvider, on_delete=models.PROTECT,
        related_name="reconciliation",
    )
    internal_reference = models.CharField(max_length=128, db_index=True)
    external_reference = models.CharField(max_length=128, blank=True, default="")
    internal_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    external_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    internal_status = models.CharField(max_length=32, blank=True, default="")
    external_status = models.CharField(max_length=32, blank=True, default="")
    status = models.CharField(
        max_length=24, choices=ReconciliationStatus.choices,
        default=ReconciliationStatus.PENDING, db_index=True,
    )
    notes = models.TextField(blank=True, default="")
    reviewed_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reconciliations_reviewed",
    )
    checked_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-checked_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "internal_reference"],
                name="unique_recon_per_reference",
            )
        ]
