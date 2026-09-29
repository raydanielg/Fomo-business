"""Entitlement system — plan gating, permissions, scope, exports, schedules."""

import pytest

from apps.accounts.models import User
from apps.branches.models import Branch
from apps.businesses.services import create_business
from apps.memberships.models import Membership
from apps.reports.models import EntitlementEvent, Report, ReportUsage, ScheduledReport
from apps.roles.models import Role
from apps.subscriptions.models import Plan, PlanFeature, Feature, UsageRecord
from apps.subscriptions.services import change_plan, get_subscription, seed_default_plans

from .conftest import auth_client


@pytest.fixture
def manager_membership(business, db):
    u = User.objects.create_user(email="mgr@a.test", password="Passw0rd!x")
    role = Role.objects.get(business=business, code="MANAGER")
    return Membership.objects.create(
        user=u, business=business, role=role,
        status=Membership.Status.ACTIVE,
    )


@pytest.fixture
def branch_b(business):
    return Branch.objects.create(business=business, name="Second", code="B2")


@pytest.fixture
def scoped_cashier(business, branch):
    """Cashier restricted to one branch (allowed_branches)."""
    u = User.objects.create_user(email="cashier2@a.test", password="Passw0rd!x")
    role = Role.objects.get(business=business, code="CASHIER")
    m = Membership.objects.create(
        user=u, business=business, role=role,
        status=Membership.Status.ACTIVE,
    )
    m.allowed_branches.set([branch])
    return m


def _upgrade(business, code):
    change_plan(business, code)


@pytest.mark.django_db
class TestPlanGating:
    def test_free_plan_report_access(self, user, business):
        client = auth_client(user, business)
        # FREE includes reports.sales
        assert client.get("/api/v1/reports/sales.summary/").status_code == 200
        assert client.get("/api/v1/reports/inventory.summary/").status_code == 200
        # FREE does NOT include profit/expenses/customers
        for key in ("profit.summary", "expenses.summary", "customers.summary"):
            resp = client.get(f"/api/v1/reports/{key}/")
            assert resp.status_code == 402, key
            assert resp.json()["error"]["code"] == "FEATURE_NOT_INCLUDED"

    def test_starter_matrix(self, user, business):
        _upgrade(business, "STARTER")
        client = auth_client(user, business)
        for key in ("sales.summary", "expenses.summary",
                    "inventory.summary", "customers.summary"):
            assert client.get(f"/api/v1/reports/{key}/").status_code == 200, key
        assert client.get("/api/v1/reports/profit.summary/").status_code == 402

    def test_business_matrix(self, user, business):
        _upgrade(business, "BUSINESS")
        client = auth_client(user, business)
        for key in ("sales.summary", "profit.summary", "expenses.summary",
                    "customers.summary", "payments.summary",
                    "staff.performance", "suppliers.summary", "tax.summary"):
            assert client.get(f"/api/v1/reports/{key}/").status_code == 200, key
        # branches/advanced still denied
        assert client.get("/api/v1/reports/branches.performance/").status_code == 402
        assert client.get("/api/v1/reports/advanced.sales_trends/").status_code == 402

    def test_pro_matrix(self, user, business):
        _upgrade(business, "PRO")
        client = auth_client(user, business)
        for key in ("branches.performance", "advanced.sales_trends",
                    "advanced.business_comparison"):
            assert client.get(f"/api/v1/reports/{key}/").status_code == 200, key

    def test_downgrade_immediately_revokes(self, user, business):
        _upgrade(business, "PRO")
        client = auth_client(user, business)
        assert client.get("/api/v1/reports/profit.summary/").status_code == 200
        _upgrade(business, "FREE")
        assert client.get("/api/v1/reports/profit.summary/").status_code == 402

    def test_upgrade_immediately_enables(self, user, business):
        client = auth_client(user, business)
        assert client.get("/api/v1/reports/profit.summary/").status_code == 402
        _upgrade(business, "BUSINESS")
        assert client.get("/api/v1/reports/profit.summary/").status_code == 200


@pytest.mark.django_db
class TestPermissionAndScope:
    def test_no_permission_even_with_plan(self, business, db):
        """STAFF lacks reports.profit perm — denied even on PRO."""
        _upgrade(business, "PRO")
        u = User.objects.create_user(email="staff@a.test", password="Passw0rd!x")
        role = Role.objects.get(business=business, code="STAFF")
        Membership.objects.create(
            user=u, business=business, role=role,
            status=Membership.Status.ACTIVE,
        )
        client = auth_client(u, business)
        resp = client.get("/api/v1/reports/profit.summary/")
        assert resp.status_code == 403
        assert resp.json()["error"]["details"]["reason"] == "PERMISSION_DENIED"
        # but staff CAN see sales reports (perm reports.sales)
        assert client.get("/api/v1/reports/sales.summary/").status_code == 200

    def test_manager_can_view_profit(self, business, manager_membership):
        _upgrade(business, "BUSINESS")
        client = auth_client(manager_membership.user, business)
        assert client.get("/api/v1/reports/profit.summary/").status_code == 200

    def test_branch_scope_denied(self, business, scoped_cashier, branch_b):
        _upgrade(business, "PRO")
        client = auth_client(scoped_cashier.user, business)
        resp = client.get(f"/api/v1/reports/sales.summary/?branch={branch_b.id}")
        assert resp.status_code == 403

    def test_branch_scope_allowed(self, business, scoped_cashier, branch):
        client = auth_client(scoped_cashier.user, business)
        resp = client.get(f"/api/v1/reports/sales.summary/?branch={branch.id}")
        assert resp.status_code == 200

    def test_cross_tenant_report_isolation(self, user, business_b):
        """User of business A hitting reports under business B context."""
        client = auth_client(user, business_b)  # not a member → middleware rejects
        resp = client.get("/api/v1/reports/sales.summary/")
        assert resp.status_code in (400, 403)

    def test_suspended_membership_denied(self, business, cashier_membership):
        cashier_membership.status = Membership.Status.SUSPENDED
        cashier_membership.save()
        client = auth_client(cashier_membership.user, business)
        resp = client.get("/api/v1/reports/sales.summary/")
        assert resp.status_code in (400, 403)


@pytest.mark.django_db
class TestCapabilitiesAndCatalog:
    def test_catalog_lists_access(self, user, business):
        client = auth_client(user, business)
        resp = client.get("/api/v1/reports/")
        assert resp.status_code == 200
        data = resp.json()["data"]
        by_key = {r["report"]["key"]: r for r in data}
        assert by_key["sales.summary"]["access"]["allowed"] is True
        assert by_key["profit.summary"]["access"]["allowed"] is False
        assert by_key["profit.summary"]["access"]["reason"] == "FEATURE_NOT_INCLUDED"
        assert by_key["profit.summary"]["access"]["upgrade_available"] is True

    def test_capabilities_endpoint(self, user, business):
        _upgrade(business, "PRO")
        client = auth_client(user, business)
        resp = client.get("/api/v1/reports/sales.summary/capabilities/")
        data = resp.json()["data"]
        assert data["access"]["allowed"] is True
        caps = data["capabilities"]
        assert caps["view"] and caps["filter"] and caps["export"]
        assert "pdf" in data["export_formats"]

    def test_capabilities_free_plan(self, user, business):
        client = auth_client(user, business)
        resp = client.get("/api/v1/reports/sales.summary/capabilities/")
        caps = resp.json()["data"]["capabilities"]
        # FREE: view/filter yes; export not entitled
        assert caps["view"] is True
        assert caps["export"] is False
        assert caps["schedule"] is False
        assert caps["compare"] is False

    def test_filters_endpoint(self, user, business):
        client = auth_client(user, business)
        resp = client.get("/api/v1/reports/sales.summary/filters/")
        assert resp.status_code == 200
        assert "start_date" in resp.json()["data"]["filters"]

    def test_advanced_filters_stripped_without_feature(self, user, business):
        client = auth_client(user, business)
        # advanced.sales_trends supports premium filters but plan lacks feature
        resp = client.get("/api/v1/reports/advanced.sales_trends/filters/")
        filters = resp.json()["data"]["filters"]
        assert "group_by" not in filters
        assert "compare" not in filters


@pytest.mark.django_db
class TestExports:
    def test_export_denied_on_free(self, user, business):
        client = auth_client(user, business)
        resp = client.post("/api/v1/reports/sales.summary/export/",
                           {"format": "csv"}, format="json")
        assert resp.status_code == 402

    def test_csv_export_starter(self, user, business):
        _upgrade(business, "STARTER")
        client = auth_client(user, business)
        resp = client.post("/api/v1/reports/sales.summary/export/",
                           {"format": "csv"}, format="json")
        assert resp.status_code == 200
        assert resp["Content-Type"] == "text/csv"
        assert "attachment" in resp["Content-Disposition"]

    def test_xlsx_blocked_on_starter(self, user, business):
        _upgrade(business, "STARTER")
        client = auth_client(user, business)
        resp = client.post("/api/v1/reports/sales.summary/export/",
                           {"format": "xlsx"}, format="json")
        assert resp.status_code == 402
        assert resp.json()["error"]["details"]["reason"] == "FORMAT_NOT_INCLUDED"

    def test_pdf_export_on_pro(self, user, business):
        _upgrade(business, "PRO")
        client = auth_client(user, business)
        resp = client.post("/api/v1/reports/sales.summary/export/",
                           {"format": "pdf"}, format="json")
        assert resp.status_code == 200
        assert resp["Content-Type"] == "application/pdf"

    def test_export_monthly_limit(self, user, business):
        _upgrade(business, "STARTER")
        # set a tiny limit
        pf = PlanFeature.objects.get(
            plan__code="STARTER", feature__key="reports.export")
        pf.configuration["max_exports_per_month"] = 1
        pf.save()

        client = auth_client(user, business)
        assert client.post("/api/v1/reports/sales.summary/export/",
                           {"format": "csv"}).status_code == 200
        resp = client.post("/api/v1/reports/sales.summary/export/",
                           {"format": "csv"})
        assert resp.status_code == 402
        err = resp.json()["error"]
        assert err["code"] == "PLAN_LIMIT_REACHED"
        assert err["details"]["used"] == 1

    def test_export_is_audited(self, user, business):
        _upgrade(business, "STARTER")
        client = auth_client(user, business)
        client.post("/api/v1/reports/sales.summary/export/", {"format": "csv"})
        assert ReportUsage.objects.filter(
            business=business, report_key="sales.summary",
            action="export", format="csv",
        ).exists()

    def test_entitlement_events_recorded(self, user, business):
        client = auth_client(user, business)
        client.get("/api/v1/reports/profit.summary/")
        assert EntitlementEvent.objects.filter(
            business=business, report_key="profit.summary",
            event_type="access_denied", reason="FEATURE_NOT_INCLUDED",
        ).exists()


@pytest.mark.django_db
class TestScheduledReports:
    def _payload(self, business, user):
        return {
            "report_key": "sales.summary",
            "recipient_ids": [str(user.id)],
            "frequency": "weekly",
            "day_of_week": 0,
            "hour": 8,
            "format": "csv",
        }

    def test_create_requires_feature(self, user, business):
        client = auth_client(user, business)
        resp = client.post("/api/v1/scheduled-reports/",
                           self._payload(business, user), format="json")
        assert resp.status_code == 402

    def test_create_on_pro(self, user, business):
        _upgrade(business, "PRO")
        client = auth_client(user, business)
        resp = client.post("/api/v1/scheduled-reports/",
                           self._payload(business, user), format="json")
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["status"] == "active"
        assert data["next_run_at"] is not None

    def test_recipient_must_be_member(self, user, business, user_b):
        _upgrade(business, "PRO")
        client = auth_client(user, business)
        payload = self._payload(business, user)
        payload["recipient_ids"] = [str(user_b.id)]  # not a member
        resp = client.post("/api/v1/scheduled-reports/", payload, format="json")
        assert resp.status_code == 400

    def test_scheduled_count_limit(self, user, business):
        _upgrade(business, "PRO")
        pf = PlanFeature.objects.get(
            plan__code="PRO", feature__key="reports.scheduled")
        pf.configuration["max_scheduled_reports"] = 1
        pf.save()
        client = auth_client(user, business)
        assert client.post("/api/v1/scheduled-reports/",
                           self._payload(business, user),
                           format="json").status_code == 201
        resp = client.post("/api/v1/scheduled-reports/",
                           self._payload(business, user), format="json")
        assert resp.status_code == 402

    def test_recipient_without_report_permission_rejected(
        self, user, business, cashier_membership
    ):
        """Cashier may not receive profit reports — permission applies to
        recipients too, not just the scheduler."""
        _upgrade(business, "PRO")
        client = auth_client(user, business)
        resp = client.post("/api/v1/scheduled-reports/", {
            "report_key": "profit.summary",
            "recipient_ids": [str(cashier_membership.user_id)],
            "frequency": "daily", "format": "csv",
        }, format="json")
        assert resp.status_code == 403
        assert resp.json()["error"]["details"]["reason"] == "PERMISSION_DENIED"

    def test_cashier_cannot_schedule(self, business, cashier_membership):
        _upgrade(business, "PRO")
        client = auth_client(cashier_membership.user, business)
        resp = client.post("/api/v1/scheduled-reports/", {
            "report_key": "sales.summary",
            "recipient_ids": [str(cashier_membership.user_id)],
            "frequency": "daily", "format": "csv",
        }, format="json")
        # cashier lacks reports.schedule permission
        assert resp.status_code == 403

    def test_run_due_scheduled_report(self, user, business):
        from apps.notifications.tasks import run_due_scheduled_reports

        _upgrade(business, "PRO")
        sched = ScheduledReport.objects.create(
            business=business,
            report=Report.objects.get(key="sales.summary"),
            creator=user, frequency="daily", hour=8, format="csv",
        )
        sched.recipients.set([user])
        from django.utils import timezone
        sched.next_run_at = timezone.now()
        sched.save()

        ran = run_due_scheduled_reports()
        assert ran == 1
        sched.refresh_from_db()
        assert sched.last_run_at is not None
        assert sched.next_run_at > timezone.now()

    def test_schedule_disabled_when_feature_lost(self, user, business):
        from apps.notifications.tasks import run_due_scheduled_reports

        _upgrade(business, "PRO")
        sched = ScheduledReport.objects.create(
            business=business,
            report=Report.objects.get(key="sales.summary"),
            creator=user, frequency="daily", hour=8, format="csv",
        )
        sched.recipients.set([user])
        from django.utils import timezone
        sched.next_run_at = timezone.now()
        sched.save()

        _upgrade(business, "FREE")  # loses reports.scheduled
        run_due_scheduled_reports()
        sched.refresh_from_db()
        assert sched.status == ScheduledReport.Status.DISABLED


@pytest.mark.django_db
class TestComparisonAndAnalytics:
    def test_plan_comparison_public(self):
        from rest_framework.test import APIClient

        resp = APIClient().get("/api/v1/subscriptions/plans/comparison/")
        assert resp.status_code == 200
        data = resp.json()["data"]
        plans = {p["code"]: p for p in data["plans"]}
        assert "FREE" in plans and "PRO" in plans
        assert "reports.profit" in plans["PRO"]["features"]
        assert "reports.profit" not in plans["FREE"]["features"]
        assert plans["PRO"]["features"]["reports.export"]["formats"] == [
            "csv", "xlsx", "pdf"]

    def test_usage_analytics_scoped(self, user, business, business_b, user_b):
        client = auth_client(user, business)
        client.get("/api/v1/reports/sales.summary/")
        resp = client.get("/api/v1/reports/analytics/")
        assert resp.status_code == 200
        viewed = {r["report_key"] for r in resp.json()["data"]["most_viewed"]}
        assert "sales.summary" in viewed

        client_b = auth_client(user_b, business_b)
        resp = client_b.get("/api/v1/reports/analytics/")
        viewed_b = {r["report_key"] for r in resp.json()["data"]["most_viewed"]}
        assert "sales.summary" not in viewed_b
