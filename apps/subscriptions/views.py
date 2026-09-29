from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import APIError, ErrorCode
from apps.common.permissions import HasActiveMembership, HasPermission

from .models import Plan, Subscription, UsageRecord
from .serializers import (
    ChangePlanSerializer,
    PlanSerializer,
    SubscriptionSerializer,
    UsageRecordSerializer,
)
from . import services


class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    """Public catalog of plans."""

    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get_queryset(self):
        return Plan.objects.filter(is_active=True)

    @action(detail=False, methods=["get"], url_path="comparison")
    def comparison(self, request):
        """Full feature matrix — frontend builds the pricing page from this."""
        plans = (
            Plan.objects.filter(is_active=True, is_public=True)
            .prefetch_related("plan_features__feature")
            .order_by("sort_order")
        )
        # collect the union of features across plans, in catalog order
        from .models import Feature

        all_features = {
            f.key: {"key": f.key, "name": f.name,
                    "category": f.category, "description": f.description}
            for f in Feature.objects.filter(is_active=True)
        }
        plan_data = []
        for plan in plans:
            entitled = {}
            for pf in plan.plan_features.all():
                if pf.enabled and pf.feature.is_active:
                    entitled[pf.feature.key] = pf.configuration or True
            plan_data.append({
                "code": plan.code, "name": plan.name,
                "description": plan.description,
                "price_monthly": plan.price_monthly,
                "price_yearly": plan.price_yearly,
                "currency": plan.currency,
                "billing_interval": plan.billing_interval,
                "limits": plan.limits,
                "features": entitled,
            })
        return Response({
            "success": True,
            "data": {
                "features": list(all_features.values()),
                "plans": plan_data,
            },
        })


class CurrentSubscriptionView(APIView):
    permission_classes = [HasActiveMembership, HasPermission]
    required_permission = "subscription.view"
    serializer_class = SubscriptionSerializer

    def get(self, request):
        sub = services.get_subscription(request.business)
        if sub is None:
            raise APIError("No subscription.", code=ErrorCode.NOT_FOUND, status_code=404)
        return Response({"success": True, "data": SubscriptionSerializer(sub).data})


class ChangePlanView(APIView):
    permission_classes = [HasActiveMembership, HasPermission]
    required_permission = "subscription.manage"
    serializer_class = ChangePlanSerializer

    def post(self, request):
        serializer = ChangePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            sub = services.change_plan(
                request.business,
                serializer.validated_data["plan_code"].upper(),
                user=request.user,
            )
        except Plan.DoesNotExist:
            raise APIError("Plan not found.", code=ErrorCode.NOT_FOUND, status_code=404)
        sub.interval = serializer.validated_data["interval"]
        sub.save(update_fields=["interval"])
        return Response({"success": True, "data": SubscriptionSerializer(sub).data})


class UsageView(APIView):
    permission_classes = [HasActiveMembership, HasPermission]
    required_permission = "subscription.view"
    serializer_class = UsageRecordSerializer

    def get(self, request):
        from django.utils import timezone

        period = timezone.now().date().replace(day=1)
        records = UsageRecord.objects.filter(
            business=request.business, period=period
        )
        sub = services.get_subscription(request.business)
        return Response(
            {
                "success": True,
                "data": {
                    "period": period,
                    "plan": sub.plan.code if sub else None,
                    "limits": sub.plan.limits if sub else {},
                    "usage": UsageRecordSerializer(records, many=True).data,
                },
            }
        )
