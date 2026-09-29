"""Authentication services — token issuing, sessions, email flows."""

import logging
import secrets
from datetime import timedelta

from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditLog
from apps.audit.services import log as audit_log

from .models import AuthToken, DeviceSession

logger = logging.getLogger("fomo.accounts")

VERIFY_TOKEN_TTL = timedelta(hours=24)
RESET_TOKEN_TTL = timedelta(hours=1)


def issue_tokens(user, *, device_name="", ip_address=None, user_agent=""):
    """Create a refresh+access pair and register a device session."""
    refresh = RefreshToken.for_user(user)
    jti = refresh["jti"]
    DeviceSession.objects.create(
        user=user,
        refresh_jti=jti,
        device_name=device_name or "Unknown device",
        ip_address=ip_address,
        user_agent=user_agent[:512] if user_agent else "",
    )
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def revoke_session(user, jti):
    DeviceSession.objects.filter(user=user, refresh_jti=jti).update(
        revoked_at=timezone.now()
    )


def create_auth_token(user, purpose):
    """Single-use opaque token for email verify / password reset."""
    ttl = VERIFY_TOKEN_TTL if purpose == AuthToken.Purpose.EMAIL_VERIFY else RESET_TOKEN_TTL
    return AuthToken.objects.create(
        user=user,
        token=secrets.token_urlsafe(32),
        purpose=purpose,
        expires_at=timezone.now() + ttl,
    )


def consume_auth_token(token_value, purpose):
    """Return the token if valid, marking it used. None otherwise."""
    try:
        token = AuthToken.objects.select_related("user").get(
            token=token_value, purpose=purpose
        )
    except AuthToken.DoesNotExist:
        return None
    if not token.is_valid():
        return None
    token.used_at = timezone.now()
    token.save(update_fields=["used_at"])
    return token


def verify_email(token_value):
    token = consume_auth_token(token_value, AuthToken.Purpose.EMAIL_VERIFY)
    if token is None:
        return False
    token.user.is_verified = True
    token.user.save(update_fields=["is_verified"])
    return True


def reset_password(token_value, new_password):
    token = consume_auth_token(token_value, AuthToken.Purpose.PASSWORD_RESET)
    if token is None:
        return False
    user = token.user
    user.set_password(new_password)
    user.save(update_fields=["password"])
    # Kill all sessions after a password reset
    user.sessions.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
    audit_log(
        AuditLog.Action.PASSWORD_RESET,
        user=user,
        resource_type="User",
        resource_id=user.id,
    )
    return True


def change_password(user, new_password):
    user.set_password(new_password)
    user.save(update_fields=["password"])
    user.sessions.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
    audit_log(
        AuditLog.Action.PASSWORD_CHANGE,
        user=user,
        resource_type="User",
        resource_id=user.id,
    )


def request_account_deletion(user):
    user.deletion_requested_at = timezone.now()
    user.save(update_fields=["deletion_requested_at"])
