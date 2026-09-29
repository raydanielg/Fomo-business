"""Provider abstraction — the rest of the billing system talks to this
interface, never to provider-specific payloads."""

from dataclasses import dataclass, field


@dataclass
class ProviderResult:
    """Normalized result of any provider call."""

    ok: bool
    status: str = ""           # normalized status or raw provider status
    reference: str = ""        # provider reference
    amount: str | None = None
    currency: str = "TZS"
    fee: str | None = None
    net: str | None = None
    error: str = ""
    raw: dict = field(default_factory=dict)


class PaymentProviderClient:
    """Interface every provider client implements."""

    code = ""

    def create_payment(self, *, amount, currency, phone, reference,
                       idempotency_key, **kw) -> ProviderResult:
        raise NotImplementedError

    def get_payment(self, reference: str) -> ProviderResult:
        raise NotImplementedError

    def create_session(self, *, amount, currency, reference,
                       idempotency_key, **kw) -> ProviderResult:
        raise NotImplementedError

    def get_session(self, reference: str) -> ProviderResult:
        raise NotImplementedError

    def create_payout(self, *, amount, currency, recipient, reference,
                      idempotency_key, **kw) -> ProviderResult:
        raise NotImplementedError

    def balance(self) -> ProviderResult:
        raise NotImplementedError

    def verify_webhook(self, *, raw_body: bytes, signature: str,
                       timestamp: str) -> bool:
        """Verify the webhook signature on the RAW body — never parse and
        reserialize before verifying."""
        raise NotImplementedError
