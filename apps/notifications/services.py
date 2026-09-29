"""NotificationService — in-app notifications + outbound delivery."""

import logging

from django.utils import timezone

from .models import Notification
from .providers import get_sms_provider, get_whatsapp_provider

logger = logging.getLogger("fomo.notifications")


def notify(user, *, type, title, message, business=None, data=None):
    """Create an in-app notification."""
    return Notification.objects.create(
        user=user,
        business=business,
        type=type,
        title=title,
        message=message,
        data=data or {},
    )


def notify_business_members(business, *, type, title, message, data=None,
                            permission=None):
    """Fan out an in-app notification to active members of a business."""
    from apps.memberships.models import Membership

    qs = Membership.objects.filter(
        business=business, status=Membership.Status.ACTIVE
    ).select_related("user", "role")
    if permission:
        qs = [m for m in qs if m.has_permission(permission)]
    notifications = [
        Notification(
            user=m.user, business=business, type=type,
            title=title, message=message, data=data or {},
        )
        for m in qs
    ]
    return Notification.objects.bulk_create(notifications)


def mark_read(notification, user=None):
    notification.read_at = timezone.now()
    notification.save(update_fields=["read_at"])
    return notification


def send_sms(to, message, *, business=None):
    """Outbound SMS via the configured provider. Usage is metered."""
    provider = get_sms_provider()
    result = provider.send(to=to, message=message)
    if business is not None:
        from apps.subscriptions.services import increment_usage
        from apps.subscriptions.models import UsageRecord

        increment_usage(business, UsageRecord.Metric.SMS_COUNT)
    return result


def send_whatsapp(to, message, *, business=None):
    provider = get_whatsapp_provider()
    result = provider.send(to=to, message=message)
    if business is not None:
        from apps.subscriptions.services import increment_usage
        from apps.subscriptions.models import UsageRecord

        increment_usage(business, UsageRecord.Metric.WHATSAPP_COUNT)
    return result
