from django.contrib import admin

from .models import (
    Feature, Plan, PlanFeature, Subscription, SubscriptionEvent, UsageRecord,
)


class PlanFeatureInline(admin.TabularInline):
    model = PlanFeature
    extra = 0
    autocomplete_fields = ["feature"]


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "price_monthly", "price_yearly",
                    "billing_interval", "is_active", "is_public", "sort_order"]
    list_filter = ["is_active", "is_public", "billing_interval"]
    search_fields = ["code", "name"]
    inlines = [PlanFeatureInline]


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ["key", "name", "category", "feature_type", "is_active"]
    list_filter = ["category", "feature_type", "is_active"]
    search_fields = ["key", "name"]


@admin.register(PlanFeature)
class PlanFeatureAdmin(admin.ModelAdmin):
    list_display = ["plan", "feature", "enabled"]
    list_filter = ["plan", "enabled", "feature__category"]
    search_fields = ["plan__code", "feature__key"]
    autocomplete_fields = ["feature"]


class SubscriptionEventInline(admin.TabularInline):
    model = SubscriptionEvent
    extra = 0
    readonly_fields = ["event_type", "old_plan", "new_plan", "created_at"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["business", "plan", "status", "interval", "current_period_end"]
    list_filter = ["status", "plan", "interval"]
    search_fields = ["business__name"]
    inlines = [SubscriptionEventInline]


@admin.register(UsageRecord)
class UsageRecordAdmin(admin.ModelAdmin):
    list_display = ["business", "metric", "period", "value"]
    list_filter = ["metric", "period"]
    search_fields = ["business__name"]
