"""Celery tasks for async notification delivery + scheduled jobs."""

import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("fomo.notifications")


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_verification_email(self, user_id, token):
    from apps.accounts.models import User
    from .providers import get_email_provider

    try:
        user = User.objects.get(id=user_id)
        link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        get_email_provider().send(
            to=user.email,
            subject="Verify your Fomo account",
            message=(
                f"Hello {user.first_name or user.email},\n\n"
                f"Welcome to Fomo. Verify your email: {link}\n\n"
                "This link expires in 24 hours."
            ),
        )
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_password_reset_email(self, user_id, token):
    from apps.accounts.models import User
    from .providers import get_email_provider

    try:
        user = User.objects.get(id=user_id)
        link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        get_email_provider().send(
            to=user.email,
            subject="Reset your Fomo password",
            message=(
                f"Hello {user.first_name or user.email},\n\n"
                f"Reset your password: {link}\n\n"
                "This link expires in 1 hour. If you didn't request this, ignore it."
            ),
        )
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_invite_email(self, user_id, business_name, token, inviter_name=""):
    from apps.accounts.models import User
    from .providers import get_email_provider

    try:
        user = User.objects.get(id=user_id)
        link = f"{settings.FRONTEND_URL}/accept-invite?token={token}"
        get_email_provider().send(
            to=user.email,
            subject=f"You're invited to {business_name} on Fomo",
            message=(
                f"{inviter_name or 'A colleague'} invited you to join "
                f"{business_name} on Fomo.\n\n"
                f"Accept and set your password: {link}\n\n"
                "This link expires in 24 hours."
            ),
        )
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_sms_task(self, to, message, business_id=None):
    from apps.businesses.models import Business
    from .services import send_sms

    business = (
        Business.objects.filter(id=business_id).first() if business_id else None
    )
    try:
        return send_sms(to, message, business=business)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task
def check_overdue_invoices(now=None):
    """Daily — mark overdue invoices and notify business members. Idempotent."""
    from apps.invoices.models import Invoice
    from .models import Notification
    from .services import notify_business_members

    now = now or timezone.now().date()
    overdue = Invoice.objects.filter(
        status__in=[Invoice.Status.ISSUED, Invoice.Status.PARTIALLY_PAID],
        due_date__lt=now,
    )
    count = overdue.update(status=Invoice.Status.OVERDUE)
    for invoice in overdue.select_related("business", "customer")[:500]:
        notify_business_members(
            invoice.business,
            type=Notification.Type.INVOICE_OVERDUE,
            title=f"Invoice {invoice.invoice_number} overdue",
            message=(
                f"Invoice {invoice.invoice_number} for "
                f"{invoice.customer.name if invoice.customer else 'customer'} "
                f"is overdue. Balance: {invoice.balance_due}."
            ),
            data={"invoice_id": str(invoice.id)},
            permission="invoices.view",
        )
    return count


@shared_task
def check_low_stock(business_id=None):
    """Notify members about products below their low-stock threshold. Idempotent."""
    from apps.inventory.services import low_stock_products
    from .models import Notification
    from .services import notify_business_members

    qs = low_stock_products(business_id=business_id)
    by_business = {}
    for row in qs:
        by_business.setdefault(row.business_id, []).append(row)

    for business_id, products in by_business.items():
        from apps.businesses.models import Business

        business = Business.objects.filter(id=business_id).first()
        if business is None:
            continue
        names = ", ".join(p.product.name for p in products[:10])
        notify_business_members(
            business,
            type=Notification.Type.LOW_STOCK,
            title=f"{len(products)} product(s) low on stock",
            message=f"Low stock: {names}",
            data={"count": len(products)},
            permission="inventory.view",
        )
    return len(by_business)


@shared_task
def expire_subscriptions():
    """Daily — expire subscriptions past their period end."""
    from apps.subscriptions.services import expire_due_subscriptions

    return expire_due_subscriptions()


@shared_task
def aggregate_usage():
    """Daily — recompute usage counters. Idempotent (upserts by period)."""
    from apps.businesses.models import Business
    from apps.subscriptions.models import UsageRecord
    from django.utils import timezone

    period = timezone.now().date().replace(day=1)
    for business in Business.objects.filter(status="active").iterator():
        products = business.product_set.filter(is_active=True).count()
        staff = business.memberships.filter(status="active").count()
        branches = business.branch_set.filter(is_active=True).count()
        for metric, value in (
            (UsageRecord.Metric.PRODUCTS_COUNT, products),
            (UsageRecord.Metric.STAFF_COUNT, staff),
            (UsageRecord.Metric.BRANCHES_COUNT, branches),
        ):
            UsageRecord.objects.update_or_create(
                business=business, metric=metric, period=period,
                defaults={"value": value},
            )


@shared_task
def run_due_scheduled_reports():
    """Every 15 minutes — deliver scheduled reports whose next_run_at is due.

    Idempotent: next_run_at is recomputed+saved on each run; a retried run
    simply re-sends to recipients.
    """
    from apps.reports.models import ScheduledReport
    from apps.reports.services import run_scheduled_report

    due = list(
        ScheduledReport.objects.filter(
            status=ScheduledReport.Status.ACTIVE,
            next_run_at__lte=timezone.now(),
        ).select_related("business", "report", "creator")
        .prefetch_related("recipients")
    )

    ran = 0
    for sched in due:
        try:
            if run_scheduled_report(sched):
                ran += 1
        except Exception:
            logger.exception("Scheduled report %s failed", sched.id)
    return ran
