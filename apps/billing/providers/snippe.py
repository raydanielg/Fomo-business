"""Snippe payment provider client.

API version: 2026-01-25 — base URL https://api.snippe.sh.
Auth: Bearer API key (server-side only, never leaves the backend).
Writes use an Idempotency-Key header; 429 responses are retried with
bounded exponential backoff.
"""

import hashlib
import hmac
import logging
import time

import requests
from django.conf import settings

from apps.common.exceptions import APIError, ErrorCode

from .base import PaymentProviderClient, ProviderResult

logger = logging.getLogger("fomo.billing.snippe")


def _configured():
    return bool(getattr(settings, "SNIPPE_API_KEY", ""))


class SnippeClient(PaymentProviderClient):
    code = "snippe"
    BASE_URL = getattr(settings, "SNIPPE_BASE_URL", "https://api.snippe.sh")
    API_VERSION = getattr(settings, "SNIPPE_API_VERSION", "2026-01-25")
    # timestamp tolerance for replay protection (seconds)
    REPLAY_WINDOW = getattr(settings, "SNIPPE_WEBHOOK_TOLERANCE", 300)
    MAX_IDEMPOTENCY_LEN = 80

    def __init__(self):
        self._key = getattr(settings, "SNIPPE_API_KEY", "")
        self._webhook_secret = getattr(settings, "SNIPPE_WEBHOOK_SECRET", "")
        if not self._key:
            raise APIError(
                "Snippe is not configured — set SNIPPE_API_KEY.",
                code=ErrorCode.SERVICE_UNAVAILABLE, status_code=503,
            )

    # ── transport ─────────────────────────────────────────────────────────
    def _headers(self, idempotency_key: str | None = None) -> dict:
        h = {
            "Authorization": f"Bearer {self._key}",
            "Snippe-Version": self.API_VERSION,
            "Accept": "application/json",
        }
        if idempotency_key:
            h["Idempotency-Key"] = idempotency_key[: self.MAX_IDEMPOTENCY_LEN]
        return h

    def _request(self, method, path, *, json_body=None, idem=None,
                 attempts=3):
        """429/5xx → bounded exponential backoff; result normalized."""
        url = f"{self.BASE_URL}{path}"
        delay = 0.5
        for i in range(attempts):
            try:
                resp = requests.request(
                    method, url, json=json_body,
                    headers=self._headers(idem), timeout=20,
                )
            except requests.RequestException as e:
                if i == attempts - 1:
                    raise APIError(
                        "Payment provider is temporarily unavailable.",
                        code=ErrorCode.SERVICE_UNAVAILABLE, status_code=503,
                    ) from e
                time.sleep(delay)
                delay *= 2
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                if i < attempts - 1:
                    retry_after = resp.headers.get("Retry-After")
                    time.sleep(float(retry_after) if retry_after else delay)
                    delay *= 2
                    continue
            break
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if resp.status_code >= 400:
            msg = data.get("error", {}).get("message") or data.get(
                "message") or "Payment provider request failed."
            raise APIError(
                msg,
                code=ErrorCode.SERVICE_UNAVAILABLE
                if resp.status_code >= 500
                else ErrorCode.BAD_REQUEST,
                status_code=resp.status_code,
            )
        return data

    # ── payments ─────────────────────────────────────────────────────────
    def create_payment(self, *, amount, currency, phone, reference,
                       idempotency_key, **kw):
        d = self._request(
            "POST", "/v1/payments",
            json_body={
                "amount": str(amount),
                "currency": currency,
                "reference": reference,
                "customer": {"phone": phone},
            },
            idem=idempotency_key,
        )
        return self._normalize(d)

    def get_payment(self, reference):
        return self._normalize(self._request("GET", f"/v1/payments/{reference}"))

    def create_session(self, *, amount, currency, reference,
                       idempotency_key, **kw):
        d = self._request(
            "POST", "/v1/checkout/sessions",
            json_body={
                "amount": str(amount),
                "currency": currency,
                "reference": reference,
            },
            idem=idempotency_key,
        )
        return self._normalize(d)

    def get_session(self, reference):
        return self._normalize(
            self._request("GET", f"/v1/checkout/sessions/{reference}"))

    def create_payout(self, *, amount, currency, recipient, reference,
                      idempotency_key, **kw):
        d = self._request(
            "POST", "/v1/payouts",
            json_body={
                "amount": str(amount),
                "currency": currency,
                "reference": reference,
                "recipient": {"phone": recipient},
            },
            idem=idempotency_key,
        )
        return self._normalize(d)

    def balance(self):
        d = self._request("GET", "/v1/payments/balance")
        return ProviderResult(ok=True, raw=d)

    # ── webhooks ─────────────────────────────────────────────────────────
    def verify_webhook(self, *, raw_body, signature, timestamp):
        """HMAC-SHA256 of `"{timestamp}.{raw_body}"` — constant-time
        comparison, stale timestamps rejected (replay protection)."""
        if not (self._webhook_secret and signature and timestamp):
            return False
        try:
            age = abs(time.time() - float(timestamp))
        except (TypeError, ValueError):
            return False
        if age > self.REPLAY_WINDOW:
            return False
        expected = hmac.new(
            self._webhook_secret.encode(),
            f"{timestamp}.".encode() + raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ── normalization ────────────────────────────────────────────────────
    _STATUS_MAP = {
        "completed": "completed",
        "success": "completed",
        "successful": "completed",
        "succeeded": "completed",
        "pending": "pending",
        "processing": "pending",
        "initiated": "pending",
        "failed": "failed",
        "declined": "failed",
        "voided": "voided",
        "expired": "expired",
        "cancelled": "cancelled",
        "canceled": "cancelled",
        "refunded": "refunded",
        "reversed": "failed",
    }

    def _normalize(self, d: dict) -> ProviderResult:
        body = d.get("data", d)
        status = str(body.get("status", "")).lower()
        return ProviderResult(
            ok=True,
            status=self._STATUS_MAP.get(status, "pending"),
            reference=str(body.get("reference") or body.get("id") or ""),
            amount=str(body.get("amount", "")) or None,
            currency=str(body.get("currency") or "TZS"),
            fee=str(body.get("fee", "")) or None,
            net=str(body.get("net_amount") or body.get("net", "")) or None,
            raw=body,
        )


def get_client() -> PaymentProviderClient:
    """Provider registry — returns the primary configured provider."""
    return SnippeClient()
