from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connections
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import generics, views
from rest_framework.response import Response

from apps.audit.models import AuditLog
from apps.billing.models import ProviderPayment, WebhookEvent
from apps.businesses.models import Business
from apps.memberships.models import Membership
from apps.notifications.models import Notification
from apps.sales.models import Sale
from apps.subscriptions.models import Plan, Subscription, UsageRecord

from .permissions import IsPlatformAdmin
from .serializers import (
    AdminAuditLogSerializer,
    AdminBusinessDetailSerializer,
    AdminBusinessSerializer,
    AdminNotificationSerializer,
    AdminUserSerializer,
)

User = get_user_model()


def _days(n: int):
    return timezone.now() - timedelta(days=n)


def _trend(qs, days=14, date_field="created_at"):
    """Daily counts for the last N days — a list of {date, value}."""
    out = []
    for i in range(days - 1, -1, -1):
        day = (timezone.now() - timedelta(days=i)).date()
        nxt = day + timedelta(days=1)
        n = qs.filter(
            **{f"{date_field}__date__gte": day, f"{date_field}__date__lt": nxt}
        ).count()
        out.append({"date": day.isoformat(), "value": n})
    return out


def _series_sum(qs, days=14, date_field="created_at", sum_field="total"):
    out = []
    for i in range(days - 1, -1, -1):
        day = (timezone.now() - timedelta(days=i)).date()
        nxt = day + timedelta(days=1)
        v = (
            qs.filter(
                **{f"{date_field}__date__gte": day, f"{date_field}__date__lt": nxt}
            ).aggregate(s=Sum(sum_field))["s"]
            or 0
        )
        out.append({"date": day.isoformat(), "value": float(v)})
    return out


class DashboardView(views.APIView):
    """Platform-wide KPI snapshot. All figures are real DB aggregates."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        now = timezone.now()
        today = now.date()
        thirty = _days(30)

        # ── Businesses ─────────────────────────────────────────────
        biz_qs = Business.objects.all()
        biz_total = biz_qs.count()
        biz_active = biz_qs.filter(status=Business.Status.ACTIVE).count()
        biz_suspended = biz_qs.filter(status=Business.Status.SUSPENDED).count()
        biz_new_30d = biz_qs.filter(created_at__gte=thirty).count()

        # ── Users ──────────────────────────────────────────────────
        u_qs = User.objects.all()
        u_total = u_qs.count()
        u_active = u_qs.filter(is_active=True).count()
        u_new_30d = u_qs.filter(date_joined__gte=thirty).count()
        u_staff = u_qs.filter(Q(is_staff=True) | Q(is_superuser=True)).count()
        u_dau = u_qs.filter(last_login__gte=now - timedelta(days=1)).count()
        u_mau = u_qs.filter(last_login__gte=thirty).count()

        # ── Subscriptions ──────────────────────────────────────────
        s_qs = Subscription.objects.select_related("plan", "business")
        s_active = s_qs.filter(status=Subscription.Status.ACTIVE).count()
        s_trial = s_qs.filter(status=Subscription.Status.TRIALING).count()
        s_expired = s_qs.filter(status=Subscription.Status.EXPIRED).count()
        s_cancelled = s_qs.filter(status=Subscription.Status.CANCELLED).count()
        s_past_due = s_qs.filter(status=Subscription.Status.PAST_DUE).count()
        s_expiring = s_qs.filter(
            status=Subscription.Status.ACTIVE,
            current_period_end__lte=now + timedelta(days=7),
        ).count()

        # plan distribution (donut)
        plan_dist = (
            s_qs.values("plan__code", "plan__name")
            .annotate(n=Count("id"))
            .order_by("-n")[:8]
        )

        # ── Revenue (billing payments, completed only) ─────────────
        pay_qs = ProviderPayment.objects.all()
        p_total = pay_qs.count()
        p_completed = pay_qs.filter(status="completed").count()
        p_failed = pay_qs.filter(status="failed").count()
        p_pending = pay_qs.filter(status__in=["pending", "processing"]).count()
        rev = pay_qs.filter(status="completed").aggregate(
            t=Sum("amount")
        )["t"] or 0
        rev_30d = (
            pay_qs.filter(status="completed", created_at__gte=thirty).aggregate(
                t=Sum("amount")
            )["t"]
            or 0
        )

        # sales — the operational transaction stream
        sale_qs = Sale.objects.filter(status=Sale.Status.COMPLETED)
        sales_total = sale_qs.count()
        sales_today = sale_qs.filter(created_at__date=today).count()
        sales_vol = sale_qs.aggregate(t=Sum("total"))["t"] or 0

        # ── Notifications ──────────────────────────────────────────
        n_qs = Notification.objects.all()
        n_total = n_qs.count()
        n_unread = n_qs.filter(read_at__isnull=True).count()
        n_today = n_qs.filter(created_at__date=today).count()

        # ── Alerts (things needing attention) ──────────────────────
        wh_failed = WebhookEvent.objects.filter(status=WebhookEvent.Status.FAILED).count()
        alerts = []
        if p_failed > 0:
            alerts.append({
                "severity": "high",
                "title": f"{p_failed} failed payments",
                "href": "/admin/failed",
            })
        if wh_failed > 0:
            alerts.append({
                "severity": "high",
                "title": f"{wh_failed} webhook failures",
                "href": "/admin/webhooks",
            })
        if biz_suspended:
            alerts.append({
                "severity": "normal",
                "title": f"{biz_suspended} suspended businesses",
                "href": "/admin/businesses",
            })
        if s_expiring:
            alerts.append({
                "severity": "normal",
                "title": f"{s_expiring} subscriptions expire within 7 days",
                "href": "/admin/subscriptions",
            })

        return Response(
            {
                "success": True,
                "data": {
                    "businesses": {
                        "total": biz_total,
                        "active": biz_active,
                        "suspended": biz_suspended,
                        "new_30d": biz_new_30d,
                        "trend": _trend(biz_qs),
                    },
                    "users": {
                        "total": u_total,
                        "active": u_active,
                        "new_30d": u_new_30d,
                        "staff": u_staff,
                        "dau": u_dau,
                        "mau": u_mau,
                        "trend": _trend(u_qs, date_field="date_joined"),
                    },
                    "subscriptions": {
                        "active": s_active,
                        "trialing": s_trial,
                        "expired": s_expired,
                        "cancelled": s_cancelled,
                        "past_due": s_past_due,
                        "expiring_7d": s_expiring,
                        "by_plan": list(plan_dist),
                    },
                    "revenue": {
                        "total": float(rev),
                        "last_30d": float(rev_30d),
                        "payments": {
                            "total": p_total,
                            "completed": p_completed,
                            "failed": p_failed,
                            "pending": p_pending,
                        },
                        "trend": _series_sum(
                            pay_qs.filter(status="completed"), sum_field="amount"
                        ),
                    },
                    "sales": {
                        "total": sales_total,
                        "today": sales_today,
                        "volume": float(sales_vol),
                        "trend": _trend(sale_qs),
                    },
                    "notifications": {
                        "total": n_total,
                        "unread": n_unread,
                        "today": n_today,
                    },
                    "webhooks": {
                        "failed": wh_failed,
                        "total": WebhookEvent.objects.count(),
                    },
                    "alerts": alerts,
                    "generated_at": now.isoformat(),
                },
            }
        )


class GrowthView(views.APIView):
    """Long-range platform growth — businesses/users/sales per month."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        months = int(request.query_params.get("months", 12))
        months = max(1, min(months, 36))

        def monthly(qs, field):
            out = []
            now = timezone.now()
            for i in range(months - 1, -1, -1):
                start = (now - timedelta(days=30 * i)).replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                )
                end = (start + timedelta(days=32)).replace(day=1)
                n = qs.filter(**{f"{field}__gte": start, f"{field}__lt": end}).count()
                out.append({"month": start.strftime("%b %Y"), "value": n})
            return out

        return Response(
            {
                "success": True,
                "data": {
                    "businesses": monthly(Business.objects.all(), "created_at"),
                    "users": monthly(User.objects.all(), "date_joined"),
                    "sales": monthly(Sale.objects.filter(status="completed"), "created_at"),
                },
            }
        )


class BusinessesListView(generics.ListAPIView):
    serializer_class = AdminBusinessSerializer
    permission_classes = [IsPlatformAdmin]

    def get_queryset(self):
        qs = (
            Business.objects.select_related("owner", "subscription__plan")
            .annotate(
                member_count=Count("memberships", distinct=True),
                branch_count=Count("branch_set", distinct=True),
            )
            .order_by("-created_at")
        )
        q = self.request.query_params.get("q")
        status = self.request.query_params.get("status")
        btype = self.request.query_params.get("type")
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(slug__icontains=q)
                | Q(email__icontains=q)
                | Q(owner__email__icontains=q)
            )
        if status:
            qs = qs.filter(status=status)
        if btype:
            qs = qs.filter(business_type=btype)
        return qs


class BusinessDetailView(generics.RetrieveAPIView):
    serializer_class = AdminBusinessDetailSerializer
    permission_classes = [IsPlatformAdmin]
    queryset = Business.objects.select_related("owner", "subscription__plan")
    lookup_field = "pk"


class UsersListView(generics.ListAPIView):
    serializer_class = AdminUserSerializer
    permission_classes = [IsPlatformAdmin]

    def get_queryset(self):
        qs = User.objects.prefetch_related(
            "memberships__business", "memberships__role"
        ).order_by("-date_joined")
        q = self.request.query_params.get("q")
        status = self.request.query_params.get("status")
        if q:
            qs = qs.filter(
                Q(email__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
            )
        if status == "active":
            qs = qs.filter(is_active=True)
        elif status == "inactive":
            qs = qs.filter(is_active=False)
        elif status == "staff":
            qs = qs.filter(Q(is_staff=True) | Q(is_superuser=True))
        return qs


class UserDetailView(generics.RetrieveAPIView):
    serializer_class = AdminUserSerializer
    permission_classes = [IsPlatformAdmin]
    queryset = User.objects.prefetch_related(
        "memberships__business", "memberships__role"
    )
    lookup_field = "pk"


class AuditLogsView(generics.ListAPIView):
    serializer_class = AdminAuditLogSerializer
    permission_classes = [IsPlatformAdmin]

    def get_queryset(self):
        qs = AuditLog.objects.select_related("user", "business")
        q = self.request.query_params.get("q")
        action = self.request.query_params.get("action")
        biz = self.request.query_params.get("business")
        if q:
            qs = qs.filter(
                Q(user__email__icontains=q)
                | Q(action__icontains=q)
                | Q(resource_type__icontains=q)
            )
        if action:
            qs = qs.filter(action=action)
        if biz:
            qs = qs.filter(business_id=biz)
        return qs


class NotificationsListView(generics.ListAPIView):
    serializer_class = AdminNotificationSerializer
    permission_classes = [IsPlatformAdmin]

    def get_queryset(self):
        qs = Notification.objects.select_related("user", "business")
        ntype = self.request.query_params.get("type")
        unread = self.request.query_params.get("unread")
        if ntype:
            qs = qs.filter(type=ntype)
        if unread == "true":
            qs = qs.filter(read_at__isnull=True)
        return qs


class SystemHealthView(views.APIView):
    """Liveness of every backing service — real pings, not stored states."""

    permission_classes = [IsPlatformAdmin]

    def _ping_db(self):
        try:
            connections["default"].ensure_connection()
            return {"status": "operational"}
        except Exception as e:
            return {"status": "down", "error": str(e)[:200]}

    def _ping_redis(self):
        try:
            cache.set("_health", "1", 5)
            cache.get("_health")
            return {"status": "operational"}
        except Exception as e:
            return {"status": "down", "error": str(e)[:200]}

    def _ping_celery(self):
        try:
            from celery import current_app

            stats = current_app.control.inspect().stats()
            workers = len(stats or {})
            return {
                "status": "operational" if workers else "unknown",
                "workers": workers,
            }
        except Exception as e:
            return {"status": "unknown", "error": str(e)[:200]}

    def _ping_snippe(self):
        try:
            from apps.billing.providers.snippe import SnippeClient

            res = SnippeClient().balance()
            return {
                "status": "operational" if res.ok else "degraded",
                "balance": getattr(res, "raw", None),
            }
        except Exception as e:
            return {"status": "degraded", "error": str(e)[:200]}

    def get(self, request):
        return Response(
            {
                "success": True,
                "data": {
                    "checked_at": timezone.now().isoformat(),
                    "services": {
                        "api": {"status": "operational"},
                        "database": self._ping_db(),
                        "redis": self._ping_redis(),
                        "celery": self._ping_celery(),
                        "snippe": self._ping_snippe(),
                        "webhooks": {
                            "status": "operational"
                            if not WebhookEvent.objects.filter(
                                status=WebhookEvent.Status.FAILED,
                                received_at__gte=timezone.now() - timedelta(hours=1),
                            ).exists()
                            else "degraded"
                        },
                    },
                },
            }
        )


class ActivityView(views.APIView):
    """Near-real-time activity — latest audit events + notifications."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        limit = int(request.query_params.get("limit", 40))
        logs = AuditLog.objects.select_related("user", "business")[:limit]
        items = [
            {
                "id": str(l.id),
                "action": l.action,
                "actor": getattr(l.user, "email", None),
                "business": getattr(l.business, "name", None),
                "resource": l.resource_type,
                "time": l.created_at.isoformat(),
            }
            for l in logs
        ]
        return Response({"success": True, "data": {"items": items}})


class PlansView(generics.ListAPIView):
    permission_classes = [IsPlatformAdmin]

    def get_queryset(self):
        return Plan.objects.annotate(
            active_subs=Count(
                "subscriptions",
                filter=Q(subscriptions__status=Subscription.Status.ACTIVE),
            )
        ).order_by("price_monthly")

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        return Response(
            {
                "success": True,
                "data": [
                    {
                        "id": str(p.id),
                        "code": p.code,
                        "name": p.name,
                        "price_monthly": float(p.price_monthly),
                        "price_yearly": float(p.price_yearly),
                        "currency": p.currency,
                        "interval": p.billing_interval,
                        "is_active": p.is_active,
                        "is_public": p.is_public,
                        "active_subscriptions": p.active_subs,
                    }
                    for p in qs
                ],
            }
        )
