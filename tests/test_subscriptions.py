import pytest

from apps.businesses.services import create_business
from apps.subscriptions.models import Plan, Subscription, UsageRecord
from apps.subscriptions.services import (
    can_use_feature, change_plan, check_limit, enforce_limit,
    increment_usage, provision_free_subscription,
)
from apps.common.exceptions import FeatureNotAvailableError, PlanLimitReachedError

from .conftest import auth_client


@pytest.mark.django_db
class TestSubscriptions:
    def test_business_gets_free_plan(self, user, business):
        sub = Subscription.objects.get(business=business)
        assert sub.plan.code == "FREE"
        assert sub.is_active

    def test_feature_entitlement(self, user, business):
        assert can_use_feature(business, "advanced_reports") is False
        change_plan(business, "BUSINESS")
        assert can_use_feature(business, "advanced_reports") is True

    def test_product_limit_enforced(self, user, business):
        client = auth_client(user, business)
        free_plan = Plan.objects.get(code="FREE")
        # reduce limit for the test
        free_plan.limits["max_products"] = 1
        free_plan.save()

        resp = client.post("/api/v1/products/", {
            "name": "P1", "selling_price": "10",
        }, format="json")
        assert resp.status_code == 201
        resp = client.post("/api/v1/products/", {
            "name": "P2", "selling_price": "10",
        }, format="json")
        assert resp.status_code == 402
        assert resp.json()["error"]["code"] == "PLAN_LIMIT_REACHED"

    def test_usage_increment_and_check(self, user, business):
        increment_usage(business, UsageRecord.Metric.SALES_COUNT, 5)
        allowed, limit, current = check_limit(
            business, "max_monthly_sales", UsageRecord.Metric.SALES_COUNT
        )
        assert allowed and current == 5 and limit == 100

    def test_advanced_report_requires_plan(self, user, business):
        client = auth_client(user, business)
        resp = client.get("/api/v1/reports/profit.summary/")
        assert resp.status_code == 402
        assert resp.json()["error"]["code"] == "FEATURE_NOT_INCLUDED"
        change_plan(business, "PRO")
        resp = client.get("/api/v1/reports/profit.summary/")
        assert resp.status_code == 200

    def test_cashier_cannot_change_plan(
        self, business, cashier_membership
    ):
        client = auth_client(cashier_membership.user, business)
        resp = client.post("/api/v1/subscriptions/change-plan/",
                           {"plan_code": "PRO"}, format="json")
        assert resp.status_code == 403
