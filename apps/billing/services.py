"""Billing services — normalization, webhook processing, reconciliation.

Every provider event lands here, gets normalized into PaymentEvent /
ProviderPayment, and drives subscription + notification side effects.
"""

import logging
import uuid

from django.db import transaction
from django.utils import timezone

from .models import (
    CheckoutSession, NormalizedStatus, PaymentEvent, PaymentProvider,
    ProviderPayment, WebhookEvent,
)
from .providers.snippe import SnippeClient

logger = logging.getLogger("fomo.billing")


def primary_provider() -> PaymentProvider:
    """Return the configured provider row, creating it if needed."""
    provider, _ = PaymentProvider.objects.get_or_create(
        code="snippe",
        defaults={
            "name": "Snippe",
            "api_version": SnippeClient.API_VERSION,
        },
    )
    return provider


def new_reference(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


# ── webhook ingestion ───────────────────────────────────────────────────────

def record_webhook(*, provider: PaymentProvider, raw: dict,
                   signature_status: str) -> WebhookEvent:
    """Store the webhook. Duplicate (provider, event_id) → mark duplicate."""
    event_id = str(raw.get("id") or raw.get("event_id") or uuid.uuid4())
    wh, created = WebhookEvent.objects.get_or_create(
        provider=provider, event_id=event_id,
        defaults={
            "event_type": str(raw.get("type") or raw.get("event") or "unknown"),
            "signature_status": signature_status,
            "payload": raw,
            "payment_reference": str(
                (raw.get("data") or {}).get("reference")
                or raw.get("reference") or ""
            ),
        },
    )
    if not created:
        wh.status = WebhookEvent.Status.DUPLICATE
        wh.save(update_fields=["status"])
    return wh


def process_webhook(wh: WebhookEvent) -> None:
    """Normalize a verified webhook into payments/events. Idempotent."""
    if wh.status == WebhookEvent.Status.PROCESSED:
        return
    started = timezone.now()
    wh.attempts += 1
    try:
        with transaction.atomic():
            _apply_event(wh)
            wh.status = WebhookEvent.Status.PROCESSED
            wh.processed_at = timezone.now()
            wh.error = ""
    except Exception as e:  # noqa: BLE001 — record and surface
        logger.exception("webhook %s processing failed", wh.event_id)
        wh.status = WebhookEvent.Status.FAILED
        wh.error = str(e)[:500]
    wh.processing_ms = int(
        (timezone.now() - started).total_seconds() * 1000
    )
    wh.save(update_fields=["status", "attempts", "processed_at",
                           "processing_ms", "error"])


def _apply_event(wh: WebhookEvent) -> None:
    data = wh.payload.get("data") or wh.payload
    ref = str(data.get("reference") or data.get("id") or wh.payment_reference)
    if not ref:
        return

    mapping = {
        "payment.completed": (NormalizedStatus.COMPLETED,
                              PaymentEvent.Type.COMPLETED),
        "payment.failed": (NormalizedStatus.FAILED,
                           PaymentEvent.Type.FAILED),
        "payment.voided": (NormalizedStatus.VOIDED,
                           PaymentEvent.Type.VOIDED),
        "payment.expired": (NormalizedStatus.EXPIRED,
                            PaymentEvent.Type.EXPIRED),
        "payment.refunded": (NormalizedStatus.REFUNDED,
                             PaymentEvent.Type.REFUND_COMPLETED),
        "payout.completed": (None, PaymentEvent.Type.PAYOUT_COMPLETED),
        "payout.failed": (None, PaymentEvent.Type.PAYOUT_FAILED),
        "payout.reversed": (None, PaymentEvent.Type.PAYOUT_REVERSED),
    }
    payment_status, event_type = mapping.get(wh.event_type, (None, None))
    if event_type is None:
        return  # unknown event — stored, not applied

    payment = ProviderPayment.objects.filter(
        provider=wh.provider,
        reference=ref,
    ).first()
    if payment is None:
        # provider event for a payment we never saw — create a record so
        # reconciliation can flag it
        payment = ProviderPayment.objects.create(
            provider=wh.provider, reference=ref,
            external_reference=str(data.get("external_reference") or ""),
            amount=data.get("amount") or 0,
            currency=data.get("currency") or "TZS",
            status=NormalizedStatus.PENDING,
            idempotency_key=f"wh-{wh.event_id}",
            metadata=data.get("metadata") or {},
        )

    if payment_status and payment.status != payment_status:
        old = payment.status
        payment.status = payment_status
        payment.status_reason = str(data.get("failure_reason") or
                                    data.get("reason") or "")
        if payment_status == NormalizedStatus.COMPLETED:
            payment.completed_at = timezone.now()
            if data.get("fee") is not None:
                payment.fee = data["fee"]
            if data.get("net_amount") or data.get("net"):
                payment.net_amount = data.get("net_amount") or data["net"]
        payment.save(update_fields=["status", "status_reason",
                                    "completed_at", "fee", "net_amount"])
        PaymentEvent.objects.create(
            payment=payment, event_type=event_type, amount=payment.amount,
            currency=payment.currency, status=payment_status,
            source="webhook", webhook_event=wh,
            detail=f"{old} → {payment_status}",
        )
        _settle_subscription_payment(payment)


def _settle_subscription_payment(payment: ProviderPayment) -> None:
    """A completed provider payment tied to a subscription billing
    request settles it and applies the plan change."""
    from apps.subscriptions.models import BillingRequest
    from apps.subscriptions import services as sub_services

    br = BillingRequest.objects.filter(
        reference=payment.reference,
        status=BillingRequest.Status.PENDING,
    ).first()
    if br is not None:
        sub_services.settle_billing_request(br)


# ── provider health ─────────────────────────────────────────────────────────

def provider_health() -> dict:
    """Live health check — does NOT fake 'operational'; reports what the
    API actually returns."""
    try:
        client = SnippeClient()
        t0 = timezone.now()
        result = client.balance()
        ms = int((timezone.now() - t0).total_seconds() * 1000)
        provider = primary_provider()
        provider.last_success_at = timezone.now()
        provider.last_error = ""
        provider.save(update_fields=["last_success_at", "last_error"])
        return {"ok": True, "latency_ms": ms, "balance": result.raw}
    except Exception as e:
        provider = primary_provider()
        provider.last_failure_at = timezone.now()
        provider.last_error = str(e)[:300]
        provider.save(update_fields=["last_failure_at", "last_error"])
        return {"ok": False, "error": str(e)[:300]}


# ── reconciliation ──────────────────────────────────────────────────────────

def reconcile_payment(payment: ProviderPayment) -> str:
    """Compare internal record with the provider's current state."""
    from .models import ReconciliationRecord, ReconciliationStatus
    from .providers.snippe import get_client

    rec, _ = ReconciliationRecord.objects.update_or_create(
        provider=payment.provider, internal_reference=payment.reference,
        defaults={
            "payment": payment,
            "internal_amount": payment.amount,
            "internal_status": payment.status,
        },
    )
    try:
        res = get_client().get_payment(payment.reference)
    except Exception:
        rec.status = ReconciliationStatus.PENDING
        rec.save(update_fields=["status"])
        return rec.status

    if not res.reference:
        rec.status = ReconciliationStatus.MISSING_PROVIDER_RECORD
    elif str(res.amount) and str(payment.amount) != str(res.amount):
        rec.status = ReconciliationStatus.MISMATCH
        rec.external_amount = res.amount
    elif res.status != payment.status:
        rec.status = ReconciliationStatus.MISMATCH
        rec.external_status = res.status
    else:
        rec.status = ReconciliationStatus.MATCHED
    rec.external_reference = res.reference
    rec.external_status = rec.external_status or res.status
    rec.save()
    return rec.status


def close_checkout_session(session: CheckoutSession) -> None:
    """Mark a session expired/cancelled server-side."""
    if session.status == CheckoutSession.Status.OPEN:
        session.status = CheckoutSession.Status.EXPIRED
        session.save(update_fields=["status"])
