"""Coverage for expenses, customers, suppliers, reports, audit."""

from decimal import Decimal

import pytest

from apps.audit.models import AuditLog
from apps.customers.models import Customer
from apps.expenses.models import Expense, ExpenseCategory
from apps.suppliers.models import Supplier

from .conftest import auth_client


@pytest.mark.django_db
class TestExpenses:
    def test_create_expense(self, user, business, branch):
        cat = ExpenseCategory.objects.create(business=business, name="Rent")
        client = auth_client(user, business)
        resp = client.post("/api/v1/expenses/", {
            "branch_id": str(branch.id),
            "category": str(cat.id),
            "amount": "5000",
            "payment_method": "CASH",
            "description": "Shop rent",
        }, format="json")
        assert resp.status_code == 201
        assert resp.json()["data"]["amount"] == "5000.00"

        # audit logged
        assert AuditLog.objects.filter(
            business=business, action="expense.created"
        ).exists()

    def test_expense_category_isolation(
        self, user, user_b, business, business_b
    ):
        ExpenseCategory.objects.create(business=business, name="RentA")
        client_b = auth_client(user_b, business_b)
        resp = client_b.get("/api/v1/expenses/categories/")
        assert resp.json()["pagination"]["total"] == 0


@pytest.mark.django_db
class TestCustomersSuppliers:
    def test_customer_crud(self, user, business):
        client = auth_client(user, business)
        resp = client.post("/api/v1/customers/", {
            "name": "Juma", "phone": "+255700000001",
        }, format="json")
        assert resp.status_code == 201
        cid = resp.json()["data"]["id"]

        resp = client.get("/api/v1/customers/?search=juma")
        assert resp.json()["pagination"]["total"] == 1

        resp = client.get(f"/api/v1/customers/{cid}/history/")
        assert resp.status_code == 200

    def test_supplier_crud(self, user, business):
        client = auth_client(user, business)
        resp = client.post("/api/v1/suppliers/", {
            "name": "Supplier X", "phone": "+255700000002",
        }, format="json")
        assert resp.status_code == 201
        sid = resp.json()["data"]["id"]
        resp = client.get(f"/api/v1/suppliers/{sid}/history/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestReports:
    def test_dashboard(self, user, business, branch, product):
        client = auth_client(user, business)
        # make a sale so dashboard has data
        client.post("/api/v1/sales/", {
            "branch_id": str(branch.id),
            "items": [{"product_id": str(product.id), "quantity": "2"}],
            "payment": {"method": "CASH", "amount": "300"},
        }, format="json")

        resp = client.get("/api/v1/reports/dashboard/")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert Decimal(data["today"]["sales"]) == Decimal("300.00")
        assert data["totals"]["products"] == 1

    def test_sales_report(self, user, business, branch, product):
        client = auth_client(user, business)
        client.post("/api/v1/sales/", {
            "branch_id": str(branch.id),
            "items": [{"product_id": str(product.id), "quantity": "1"}],
            "payment": {"method": "CASH", "amount": "150"},
        }, format="json")
        resp = client.get("/api/v1/reports/sales.summary/")
        assert resp.status_code == 200
        assert Decimal(resp.json()["data"]["result"]["summary"]["total"]) == Decimal("150.00")

    def test_cashier_cannot_view_reports(self, business, cashier_membership):
        client = auth_client(cashier_membership.user, business)
        resp = client.get("/api/v1/reports/dashboard/")
        assert resp.status_code == 403


@pytest.mark.django_db
class TestAudit:
    def test_sale_actions_are_audited(self, user, business, branch, product):
        client = auth_client(user, business)
        client.post("/api/v1/sales/", {
            "branch_id": str(branch.id),
            "items": [{"product_id": str(product.id), "quantity": "1"}],
            "payment": {"method": "CASH", "amount": "150"},
        }, format="json")
        actions = set(
            AuditLog.objects.filter(business=business).values_list(
                "action", flat=True
            )
        )
        assert "sale.created" in actions
        assert "sale.completed" in actions
        assert "payment.received" in actions

    def test_audit_never_stores_passwords(self, user, business):
        client = auth_client(user, business)
        client.post("/api/v1/auth/change-password/", {
            "current_password": "Passw0rd!x",
            "new_password": "Secret123!",
            "new_password_confirm": "Secret123!",
        })
        for log in AuditLog.objects.filter(action="auth.password_change"):
            blob = str(log.old_values) + str(log.new_values)
            assert "Secret123" not in blob
            assert "Passw0rd" not in blob
