"""Audit service — the single entry point for recording actions."""

import logging

from .context import get_audit_context
from .models import AuditLog

logger = logging.getLogger("fomo.audit")

SENSITIVE_KEYS = {"password", "token", "secret", "api_key", "authorization"}


def _sanitize(values):
    if not isinstance(values, dict):
        return values
    return {
        k: ("***" if any(s in k.lower() for s in SENSITIVE_KEYS) else v)
        for k, v in values.items()
    }


def log(
    action,
    *,
    business=None,
    user=None,
    resource_type="",
    resource_id="",
    old_values=None,
    new_values=None,
):
    """Record an audit event. Failures are logged, never raised."""
    try:
        ctx = get_audit_context()
        return AuditLog.objects.create(
            business=business,
            user=user if getattr(user, "is_authenticated", False) else None,
            action=action,
            resource_type=resource_type or "",
            resource_id=str(resource_id or ""),
            old_values=_sanitize(old_values),
            new_values=_sanitize(new_values),
            ip_address=ctx.get("ip_address"),
            user_agent=ctx.get("user_agent") or "",
            request_id=ctx.get("request_id") or "",
        )
    except Exception:  # pragma: no cover
        logger.exception("Failed to write audit log")
        return None
