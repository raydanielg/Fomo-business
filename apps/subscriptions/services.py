"""SubscriptionService — plan provisioning, entitlements, usage metering."""

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.common.exceptions import FeatureNotAvailableError, PlanLimitReachedError

from .models import (
    BillingRequest, Feature, Plan, PlanFeature, Subscription,
    SubscriptionEvent, UsageRecord,
)

logger = logging.getLogger("fomo.subscriptions")

DEFAULT_PLANS = [
    {
        "code": "FREE",
        "name": "Free",
        "price_monthly": 0,
        "price_yearly": 0,
        "sort_order": 0,
        "limits": {"max_products": 50, "max_staff": 2, "max_branches": 1,
                   "max_monthly_sales": 100, "max_sms": 0},
        "features": {"advanced_reports": False, "multi_branch": False,
                     "api_access": False, "receipt_pdf": True},
    },
    {
        "code": "STARTER",
        "name": "Starter",
        "price_monthly": 15000,
        "price_yearly": 150000,
        "sort_order": 1,
        "limits": {"max_products": 500, "max_staff": 3, "max_branches": 1,
                   "max_monthly_sales": 1000, "max_sms": 100},
        "features": {"advanced_reports": False, "multi_branch": False,
                     "api_access": False, "receipt_pdf": True},
    },
    {
        "code": "BUSINESS",
        "name": "Business",
        "price_monthly": 40000,
        "price_yearly": 400000,
        "sort_order": 2,
        "limits": {"max_products": 5000, "max_staff": 15, "max_branches": 3,
                   "max_monthly_sales": 10000, "max_sms": 1000},
        "features": {"advanced_reports": True, "multi_branch": True,
                     "api_access": False, "receipt_pdf": True},
    },
    {
        "code": "PRO",
        "name": "Pro",
        "price_monthly": 90000,
        "price_yearly": 900000,
        "sort_order": 3,
        "limits": {"max_products": None, "max_staff": 50, "max_branches": 10,
                   "max_monthly_sales": None, "max_sms": 5000},
        "features": {"advanced_reports": True, "multi_branch": True,
                     "api_access": True, "receipt_pdf": True},
    },
    {
        "code": "ENTERPRISE",
        "name": "Enterprise",
        "price_monthly": 250000,
        "price_yearly": 2500000,
        "sort_order": 4,
        "limits": {},
        "features": {"advanced_reports": True, "multi_branch": True,
                     "api_access": True, "receipt_pdf": True,
                     "dedicated_support": True},
    },
]


def seed_default_plans():
    from apps.reports.catalog import seed_report_catalog

    for plan_data in DEFAULT_PLANS:
        Plan.objects.update_or_create(
            code=plan_data["code"], defaults=plan_data
        )
    # keep the Feature/Report catalog and PlanFeature matrix in sync
    try:
        from apps.common.management.commands.seed_reporting import DEFAULT_MATRIX

        seed_report_catalog()
        for plan_code, matrix in DEFAULT_MATRIX.items():
            plan = Plan.objects.filter(code=plan_code).first()
            if plan is None:
                continue
            for key, config in matrix.items():
                feature = Feature.objects.filter(key=key).first()
                if feature is None:
                    continue
                PlanFeature.objects.update_or_create(
                    plan=plan, feature=feature,
                    defaults={"enabled": True, "configuration": config},
                )
    except Exception:  # pragma: no cover — catalog tables may not exist yet
        logger.exception("Skipping plan-feature sync during plan seed")


def get_subscription(business):
    try:
        return business.subscription
    except Subscription.DoesNotExist:
        return None


def provision_free_subscription(business):
    plan = Plan.objects.filter(code="FREE").first()
    if plan is None:
        seed_default_plans()
        plan = Plan.objects.get(code="FREE")
    sub, _ = Subscription.objects.get_or_create(
        business=business,
        defaults={
            "plan": plan,
            "status": Subscription.Status.ACTIVE,
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=3650),
        },
    )
    return sub


def can_use_feature(business, feature_key):
    """Feature entitlement check — never scatter `plan == "PRO"` in code."""
    sub = get_subscription(business)
    if sub is None or not sub.is_active:
        return False
    return sub.plan.has_feature(feature_key)


def require_feature(business, feature_key):
    if not can_use_feature(business, feature_key):
        raise FeatureNotAvailableError(
            f"Feature '{feature_key}' is not available on your plan."
        )


def _current_period():
    today = timezone.now().date()
    return today.replace(day=1)


def get_usage(business, metric):
    record = UsageRecord.objects.filter(
        business=business, metric=metric, period=_current_period()
    ).first()
    return record.value if record else 0


def increment_usage(business, metric, amount=1):
    period = _current_period()
    with transaction.atomic():
        record, _ = UsageRecord.objects.select_for_update().get_or_create(
            business=business, metric=metric, period=period, defaults={"value": 0}
        )
        record.value = F("value") + amount
        record.save(update_fields=["value", "updated_at"])
        record.refresh_from_db(fields=["value"])
        return record.value


def check_limit(business, limit_key, metric=None, current_value=None):
    """Return (allowed: bool, limit, current)."""
    sub = get_subscription(business)
    if sub is None or not sub.is_active:
        return False, 0, 0
    limit = sub.plan.limit(limit_key)
    if limit is None:
        return True, None, 0
    current = (
        current_value
        if current_value is not None
        else get_usage(business, metric) if metric else 0
    )
    return current < limit, limit, current


def enforce_limit(business, limit_key, metric=None, current_value=None):
    allowed, limit, current = check_limit(business, limit_key, metric, current_value)
    if not allowed:
        raise PlanLimitReachedError(
            f"Plan limit '{limit_key}' reached ({current}/{limit}).",
            details={"limit": limit, "current": current},
        )


def change_plan(business, new_plan_code, *, user=None):
    from apps.audit.models import AuditLog
    from apps.audit.services import log as audit_log

    sub = get_subscription(business)
    plan = Plan.objects.get(code=new_plan_code, is_active=True)
    old_code = sub.plan.code if sub else ""
    with transaction.atomic():
        if sub is None:
            sub = Subscription.objects.create(business=business, plan=plan)
        else:
            sub.plan = plan
            sub.status = Subscription.Status.ACTIVE
            sub.save(update_fields=["plan", "status", "updated_at"])
        SubscriptionEvent.objects.create(
            subscription=sub,
            event_type="plan_changed",
            old_plan=old_code,
            new_plan=plan.code,
        )
        audit_log(
            AuditLog.Action.SUBSCRIPTION_CHANGED,
            business=business,
            user=user,
            resource_type="Subscription",
            resource_id=sub.id,
            old_values={"plan": old_code},
            new_values={"plan": plan.code},
        )
        # entitlement trail — upgraded vs downgraded by feature count
        from apps.reports.models import EntitlementEvent

        if old_code and old_code != plan.code:
            try:
                old_plan = Plan.objects.get(code=old_code)
                old_keys = set(old_plan.plan_features.filter(
                    enabled=True).values_list("feature__key", flat=True))
                new_keys = set(plan.plan_features.filter(
                    enabled=True).values_list("feature__key", flat=True))
                etype = (
                    EntitlementEvent.EventType.UPGRADED
                    if new_keys > old_keys
                    else EntitlementEvent.EventType.DOWNGRADED
                    if old_keys > new_keys
                    else EntitlementEvent.EventType.PLAN_CHANGED
                )
            except Plan.DoesNotExist:
                etype = EntitlementEvent.EventType.PLAN_CHANGED
            EntitlementEvent.objects.create(
                business=business, user=user, event_type=etype,
                metadata={"old_plan": old_code, "new_plan": plan.code},
            )
    return sub


def expire_due_subscriptions(now=None):
    now = now or timezone.now()
    expired = Subscription.objects.filter(
        status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING],
        current_period_end__lt=now,
    )
    count = expired.update(status=Subscription.Status.EXPIRED)
    return count


# ── billing / checkout ──────────────────────────────────────────────────

def create_billing_request(*, business, plan, interval, method, phone,
                           amount, currency="TZS", user=None):
    """Create a pending payment and notify the payer — this is the seam
    where a real mobile-money push (AzamPay, Selcom, M-Pesa API) would be
    invoked. The notification doubles as the 'push' the payer sees."""
    import secrets

    from .models import BillingRequest

    br = BillingRequest.objects.create(
        business=business, plan=plan, interval=interval, method=method,
        phone=phone, amount=amount, currency=currency,
        reference=f"FMO-{secrets.token_hex(4).upper()}",
        created_by=user,
    )
    try:
        from apps.notifications.services import notify
        notify(
            user or business.owner, business=business, type="subscription",
            title="Payment request sent",
            message=(
                f"Approve the {plan.get_billing_interval_display() if hasattr(plan, 'get_billing_interval_display') else ''} "
                f"{plan.name} payment of {currency} {amount} on {phone}."
            ),
            data={"reference": br.reference, "status": br.status},
        )
    except Exception:
        pass  # notification is best-effort, billing itself already recorded
    return br


def settle_billing_request(br):
    """Settle a pending request: marks it paid and applies the plan change.

    Simulates the payment-gateway confirmation webhook. Idempotent —
    calling it on a settled request returns it unchanged."""
    if br.status != BillingRequest.Status.PENDING:
        return br

    with transaction.atomic():
        br.status = BillingRequest.Status.PAID
        br.paid_at = timezone.now()
        br.save(update_fields=["status", "paid_at"])
        sub = change_plan(br.business, br.plan.code, user=br.created_by)
        sub.interval = br.interval
        sub.save(update_fields=["interval"])
    return br
