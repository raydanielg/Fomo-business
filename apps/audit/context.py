"""Per-request audit context (ip / user-agent / request id)."""

import contextvars

_ip = contextvars.ContextVar("audit_ip", default=None)
_ua = contextvars.ContextVar("audit_ua", default=None)
_rid = contextvars.ContextVar("audit_rid", default=None)


def set_audit_context(ip_address=None, user_agent=None, request_id=None):
    _ip.set(ip_address)
    _ua.set(user_agent)
    _rid.set(request_id)


def get_audit_context():
    return {
        "ip_address": _ip.get(),
        "user_agent": _ua.get(),
        "request_id": _rid.get(),
    }
