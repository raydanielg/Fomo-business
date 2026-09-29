"""Admin billing API — read-only operational console over normalized
billing records. Platform scope: superuser only."""

import json
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import permissions, status as http_status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import APIError, ErrorCode

from .models import (
    CheckoutSession, NormalizedStatus, PaymentEvent, PaymentLink,
    PaymentProvider, ProviderPayment, Payout, ReconciliationRecord,
    ReconciliationStatus, Refund, WebhookEvent,
)
from .serializers import (
    CheckoutSessionSerializer, PaymentEventSerializer, PaymentLinkSerializer,
    PaymentProviderSerializer, ProviderPaymentSerializer, PayoutSerializer,
    ReconciliationSerializer, RefundSerializer, WebhookEventSerializer,
)
from . import services
from .providers.snippe import SnippeClient


class IsPlatformAdmin(permissions.BasePermission):
    """Billing console is platform-level — staff/superuser only."""

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_staff or u.is_superuser))


def ok(data, status=http_status.HTTP_200_OK):
    return Response({"success": True, "data": data}, status=status)


def _qs_params(request):
    """Shared filters: search, status, date range."""
    return {
        "search": request.query_params.get("search", "").strip(),
        "status": request.query_params.get("status", "").strip(),
        "from": request.query_params.get("from", ""),
        "to": request.query_params.get("to", ""),
    }


def _date_filter(qs, p, field="created_at"):
    if p["from"]:
        qs = qs.filter(**{f"{field}__date__gte": p["from"]})
    if p["to"]:
        qs = qs.filter(**{f"{field}__date__lte": p["to"]})
    return qs


# ── overview / command center ─────────────────────────────────────────────

class BillingOverviewView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        now = timezone.now()
        today = now.date()
        month_start = today.replace(day=1)
        prev_month = (month_start - timedelta(days=1)).replace(day=1)

        pays = ProviderPayment.objects
        def total(qs):
            return qs.aggregate(t=Sum("amount"))["t"] or 0

        completed = pays.filter(status=NormalizedStatus.COMPLETED)
        this_month = total(completed.filter(completed_at__date__gte=month_start))
        last_month = total(completed.filter(
            completed_at__date__gte=prev_month,
            completed_at__date__lt=month_start))
        today_total = total(completed.filter(completed_at__date=today))

        status_counts = dict(
            pays.values_list("status").annotate(c=Count("id")))

        refunds_total = Refund.objects.filter(
            status=Refund.Status.COMPLETED).aggregate(
                t=Sum("amount"))["t"] or 0

        from apps.invoices.models import Invoice
        outstanding = Invoice.objects.filter(
            status__in=["issued", "partially_paid", "overdue"]).aggregate(
                t=Sum("balance_due"))["t"] or 0

        from apps.subscriptions.models import Subscription
        mrr = Subscription.objects.filter(
            status__in=["active", "trialing"]).aggregate(
                t=Sum("plan__price_monthly"))["t"] or 0

        # sparkline: last 14 days of completed revenue
        spark = (
            completed.filter(completed_at__date__gte=today - timedelta(days=13))
            .annotate(d=TruncDate("completed_at"))
            .values("d").annotate(t=Sum("amount")).order_by("d"))
        sparkline = [{"date": str(r["d"]), "total": float(r["t"])}
                     for r in spark]

        last_event = PaymentEvent.objects.first()
        last_webhook = WebhookEvent.objects.first()

        return ok({
            "date": str(today),
            "kpis": {
                "total_revenue": float(total(completed)),
                "mrr": float(mrr),
                "today_collections": float(today_total),
                "month_change_pct": round(
                    (this_month - last_month) / last_month * 100, 1
                ) if last_month else None,
                "successful": status_counts.get("completed", 0),
                "pending": status_counts.get("pending", 0),
                "failed": status_counts.get("failed", 0),
                "expired": status_counts.get("expired", 0),
                "voided": status_counts.get("voided", 0),
                "refunds": float(refunds_total),
                "outstanding_invoices": float(outstanding),
            },
            "sparkline": sparkline,
            "last_event_at": last_event.created_at if last_event else None,
            "last_webhook_at": last_webhook.received_at if last_webhook else None,
        })


# ── payments ──────────────────────────────────────────────────────────────

class AdminPaymentsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        p = _qs_params(request)
        qs = ProviderPayment.objects.select_related("business", "provider")
        qs = _date_filter(qs, p)
        if p["status"]:
            qs = qs.filter(status=p["status"])
        if p["search"]:
            from django.db.models import Q
            qs = qs.filter(
                Q(reference__icontains=p["search"])
                | Q(external_reference__icontains=p["search"])
                | Q(customer_phone__icontains=p["search"])
                | Q(customer_email__icontains=p["search"])
                | Q(customer_name__icontains=p["search"])
                | Q(business__name__icontains=p["search"]))
        page = int(request.query_params.get("page", 1))
        size = min(int(request.query_params.get("page_size", 25)), 100)
        total = qs.count()
        rows = qs[(page - 1) * size: page * size]
        return ok({
            "count": total, "page": page, "page_size": size,
            "results": ProviderPaymentSerializer(rows, many=True).data,
        })


class AdminPaymentDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request, pk):
        pay = ProviderPayment.objects.filter(id=pk).select_related(
            "business", "provider").first()
        if pay is None:
            raise APIError("Payment not found.", code=ErrorCode.NOT_FOUND,
                           status_code=404)
        events = PaymentEventSerializer(pay.events.all(), many=True).data
        return ok({
            "payment": ProviderPaymentSerializer(pay).data,
            "timeline": events,
        })


# ── sessions / links / payouts / refunds ──────────────────────────────────

class _ListView(APIView):
    permission_classes = [IsPlatformAdmin]
    model = None
    serializer = None

    def get(self, request):
        p = _qs_params(request)
        qs = _date_filter(self.model.objects.all(), p)
        if p["status"]:
            qs = qs.filter(status=p["status"])
        page = int(request.query_params.get("page", 1))
        size = min(int(request.query_params.get("page_size", 25)), 100)
        return ok({
            "count": qs.count(), "page": page, "page_size": size,
            "results": self.serializer(qs[(page - 1) * size: page * size],
                                       many=True).data,
        })


class AdminCheckoutSessionsView(_ListView):
    model = CheckoutSession
    serializer = CheckoutSessionSerializer


class AdminPaymentLinksView(_ListView):
    model = PaymentLink
    serializer = PaymentLinkSerializer


class AdminPayoutsView(_ListView):
    model = Payout
    serializer = PayoutSerializer


class AdminRefundsView(_ListView):
    model = Refund
    serializer = RefundSerializer


class AdminPaymentEventsView(_ListView):
    model = PaymentEvent
    serializer = PaymentEventSerializer


class AdminWebhooksView(_ListView):
    model = WebhookEvent
    serializer = WebhookEventSerializer


class AdminReconciliationView(_ListView):
    model = ReconciliationRecord
    serializer = ReconciliationSerializer


class AdminSubscriptionsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from apps.subscriptions.models import Subscription

        p = _qs_params(request)
        qs = Subscription.objects.select_related("business", "plan")
        qs = _date_filter(qs, p, field="created_at")
        if p["status"]:
            qs = qs.filter(status=p["status"])
        if p["search"]:
            qs = qs.filter(business__name__icontains=p["search"])
        page = int(request.query_params.get("page", 1))
        size = min(int(request.query_params.get("page_size", 25)), 100)
        rows = qs[(page - 1) * size: page * size]
        return ok({
            "count": qs.count(), "page": page, "page_size": size,
            "results": [{
                "id": str(s.id),
                "business": s.business.name,
                "plan": s.plan.name,
                "plan_code": s.plan.code,
                "amount": str(s.plan.price_yearly if s.interval == "yearly"
                              else s.plan.price_monthly),
                "currency": s.plan.currency,
                "interval": s.interval,
                "status": s.status,
                "period_start": s.current_period_start,
                "period_end": s.current_period_end,
                "is_active": s.is_active,
                "created_at": s.created_at,
            } for s in rows],
        })


class AdminInvoicesView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from apps.invoices.models import Invoice

        p = _qs_params(request)
        qs = Invoice.objects.select_related("business", "customer")
        qs = _date_filter(qs, p)
        if p["status"]:
            qs = qs.filter(status=p["status"])
        if p["search"]:
            from django.db.models import Q
            qs = qs.filter(
                Q(invoice_number__icontains=p["search"])
                | Q(business__name__icontains=p["search"])
                | Q(customer__name__icontains=p["search"]))
        page = int(request.query_params.get("page", 1))
        size = min(int(request.query_params.get("page_size", 25)), 100)
        rows = qs[(page - 1) * size: page * size]
        return ok({
            "count": qs.count(), "page": page, "page_size": size,
            "results": [{
                "id": str(i.id),
                "invoice_number": i.invoice_number,
                "business": i.business.name,
                "customer": i.customer.name if i.customer else "",
                "total": str(i.total),
                "paid": str(i.amount_paid),
                "balance_due": str(i.balance_due),
                "currency": getattr(i, "currency", "TZS") or "TZS",
                "status": i.status,
                "issue_date": str(i.issue_date) if i.issue_date else None,
                "due_date": str(i.due_date) if i.due_date else None,
                "created_at": i.created_at,
            } for i in rows],
        })


# ── providers ─────────────────────────────────────────────────────────────

class AdminProvidersView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        providers = PaymentProvider.objects.all()
        return ok({
            "configured": bool(settings.SNIPPE_API_KEY),
            "results": PaymentProviderSerializer(providers, many=True).data,
        })


class SnippeHealthView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        if not settings.SNIPPE_API_KEY:
            return ok({
                "ok": False, "configured": False,
                "error": "SNIPPE_API_KEY not configured",
            })
        return ok({"configured": True, **services.provider_health()})


class SnippeBalanceView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from .providers.snippe import get_client
        res = get_client().balance()
        return ok(res.raw)


# ── Snippe webhook receiver (public endpoint, HMAC-verified) ──────────────

from rest_framework.decorators import api_view, authentication_classes, permission_classes


@api_view(["POST"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def snippe_webhook(request):
    """Receive provider webhooks. Verify HMAC on the RAW body before
    parsing; dedup by event_id; process inline (swap to Celery task for
    fully-async processing when the worker is running)."""
    raw_body = request.body
    signature = request.headers.get("X-Webhook-Signature", "")
    timestamp = request.headers.get("X-Webhook-Timestamp", "")

    client = SnippeClient()  # 503 if not configured — key never leaves here
    if not client.verify_webhook(
            raw_body=raw_body, signature=signature, timestamp=timestamp):
        services.record_webhook(
            provider=services.primary_provider(),
            raw={"_unverified": True},
            signature_status=WebhookEvent.SignatureStatus.INVALID,
        )
        return Response({"success": False},
                        status=http_status.HTTP_401_UNAUTHORIZED)

    payload = json.loads(raw_body.decode("utf-8"))
    wh = services.record_webhook(
        provider=services.primary_provider(),
        raw=payload,
        signature_status=WebhookEvent.SignatureStatus.VERIFIED,
    )
    if wh.status != WebhookEvent.Status.DUPLICATE:
        services.process_webhook(wh)
    return ok({"received": True})


# ── subscription checkout → provider billing ───────────────────────────────

class SubscriptionPayView(APIView):
    """Tenant-facing: push a mobile-money payment for a plan through the
    provider. Creates the ProviderPayment + BillingRequest; the webhook
    completes the plan change."""

    from apps.common.permissions import HasActiveMembership, HasPermission
    permission_classes = [HasActiveMembership, HasPermission]
    required_permission = "subscription.manage"

    def post(self, request):
        phone = str(request.data.get("phone", "")).strip()
        plan_code = str(request.data.get("plan_code", "")).upper()
        interval = str(request.data.get("interval", "monthly"))
        if not phone:
            raise APIError("Phone is required.", code=ErrorCode.VALIDATION_ERROR)

        from apps.subscriptions.models import BillingRequest, Plan, Subscription
        plan = Plan.objects.filter(code=plan_code, is_active=True).first()
        if plan is None:
            raise APIError("Plan not found.", code=ErrorCode.NOT_FOUND,
                           status_code=404)
        amount = (plan.price_yearly
                  if interval == Subscription.Interval.YEARLY
                  else plan.price_monthly)

        provider = services.primary_provider()
        ref = services.new_reference("PAY")
        try:
            res = SnippeClient().create_payment(
                amount=amount, currency=plan.currency or "TZS",
                phone=phone, reference=ref, idempotency_key=ref,
            )
        except APIError:
            raise
        except Exception as e:
            raise APIError("Payment provider is temporarily unavailable.",
                           code=ErrorCode.INTERNAL_ERROR, status_code=503) from e

        with transaction.atomic():
            pay = ProviderPayment.objects.create(
                provider=provider, reference=ref,
                external_reference=res.reference,
                business=request.business,
                customer_phone=phone,
                amount=amount, currency=plan.currency or "TZS",
                status=NormalizedStatus.PENDING,
                idempotency_key=ref,
            )
            PaymentEvent.objects.create(
                payment=pay, event_type=PaymentEvent.Type.INITIATED,
                amount=amount, currency=pay.currency,
                status="pending", source="api",
            )
            BillingRequest.objects.create(
                business=request.business, plan=plan, interval=interval,
                method="MPESA", phone=phone, amount=amount,
                currency=pay.currency, reference=ref,
                created_by=request.user,
            )
        return ok({
            "reference": ref,
            "status": pay.status,
            "message": "Payment request sent. Approve on your phone.",
        }, status=http_status.HTTP_201_CREATED)
