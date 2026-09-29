from rest_framework import serializers

from .models import BillingRequest, Plan, Subscription, SubscriptionEvent, UsageRecord


class PlanSerializer(serializers.ModelSerializer):
    feature_keys = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = [
            "id", "code", "name", "description",
            "price_monthly", "price_yearly", "currency", "billing_interval",
            "limits", "features", "feature_keys",
            "is_active", "is_public", "sort_order",
        ]
        read_only_fields = fields

    def get_feature_keys(self, obj):
        """Normalized PlanFeature keys — the authoritative entitlement list."""
        return sorted(
            obj.plan_features.filter(enabled=True, feature__is_active=True)
            .values_list("feature__key", flat=True)
        )


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id", "plan", "status", "interval",
            "current_period_start", "current_period_end",
            "is_active", "cancelled_at", "created_at",
        ]
        read_only_fields = fields


class SubscriptionEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionEvent
        fields = ["id", "event_type", "old_plan", "new_plan", "metadata", "created_at"]


class UsageRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsageRecord
        fields = ["metric", "period", "value"]


class ChangePlanSerializer(serializers.Serializer):
    plan_code = serializers.CharField()
    interval = serializers.ChoiceField(
        choices=Subscription.Interval.choices, default=Subscription.Interval.MONTHLY
    )


class CheckoutSerializer(serializers.Serializer):
    plan_code = serializers.CharField()
    phone = serializers.RegexField(
        regex=r"^\+?\d{9,15}$",
        error_messages={"invalid": "Enter a valid mobile money number."},
    )
    method = serializers.ChoiceField(
        choices=BillingRequest.Method.choices,
        default=BillingRequest.Method.MPESA,
    )
    interval = serializers.ChoiceField(
        choices=Subscription.Interval.choices, default=Subscription.Interval.MONTHLY
    )


class BillingRequestSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)

    class Meta:
        model = BillingRequest
        fields = [
            "id", "reference", "plan", "interval", "method", "phone",
            "amount", "currency", "status", "created_at", "paid_at",
        ]
        read_only_fields = fields
