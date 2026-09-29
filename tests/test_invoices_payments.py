from decimal import Decimal

import pytest

from apps.customers.models import Customer
from apps.invoices.models import Invoice
from apps.payments.models import Payment

from .conftest import auth_client


@pytest.mark.django_db
class TestInvoices:
    def test_invoice_created_with_server_totals(
        self, user, business, branch, product
    ):
        customer = Customer.objects.create(business=business, name="C1")
        client = auth_client(user, business)
        resp = client.post("/api/v1/invoices/", {
            "branch_id": str(branch.id),
            "customer_id": str(customer.id),
            "items": [{
                "product_id": str(product.id), "quantity": "2",
                "unit_price": "150",
            }],
            "issue_immediately": True,
        }, format="json")
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["total"] == "300.00"
        assert data["invoice_number"].startswith("INV-")
        assert data["status"] == "issued"

    def test_invoice_numbers_unique(self, user, business, branch, product):
        client = auth_client(user, business)
        nums = set()
        for _ in range(3):
            resp = client.post("/api/v1/invoices/", {
                "branch_id": str(branch.id),
                "items": [{"product_id": str(product.id), "quantity": "1",
                           "unit_price": "100"}],
            }, format="json")
            nums.add(resp.json()["data"]["invoice_number"])
        assert len(nums) == 3

    def test_invoice_payment_updates_balance(
        self, user, business, branch, product
    ):
        customer = Customer.objects.create(business=business, name="C2")
        client = auth_client(user, business)
        resp = client.post("/api/v1/invoices/", {
            "branch_id": str(branch.id),
            "customer_id": str(customer.id),
            "items": [{"product_id": str(product.id), "quantity": "4",
                       "unit_price": "100"}],
            "issue_immediately": True,
        }, format="json")
        invoice_id = resp.json()["data"]["id"]

        customer.refresh_from_db()
        assert customer.current_balance == Decimal("400.00")

        resp = client.post(f"/api/v1/invoices/{invoice_id}/record-payment/", {
            "amount": "400", "method": "MOBILE_MONEY", "reference": "MPE123",
        }, format="json")
        assert resp.status_code == 201

        invoice = Invoice.objects.get(id=invoice_id)
        assert invoice.status == "paid"
        assert invoice.balance_due == Decimal("0.00")
        customer.refresh_from_db()
        assert customer.current_balance == Decimal("0.00")

    def test_overpayment_rejected(self, user, business, branch, product):
        client = auth_client(user, business)
        resp = client.post("/api/v1/invoices/", {
            "branch_id": str(branch.id),
            "items": [{"product_id": str(product.id), "quantity": "1",
                       "unit_price": "100"}],
            "issue_immediately": True,
        }, format="json")
        invoice_id = resp.json()["data"]["id"]
        resp = client.post(f"/api/v1/invoices/{invoice_id}/record-payment/", {
            "amount": "500", "method": "CASH",
        }, format="json")
        assert resp.status_code == 400

    def test_cancel_invoice_releases_balance(
        self, user, business, branch, product
    ):
        customer = Customer.objects.create(business=business, name="C3")
        client = auth_client(user, business)
        resp = client.post("/api/v1/invoices/", {
            "branch_id": str(branch.id), "customer_id": str(customer.id),
            "items": [{"product_id": str(product.id), "quantity": "2",
                       "unit_price": "100"}],
            "issue_immediately": True,
        }, format="json")
        invoice_id = resp.json()["data"]["id"]
        customer.refresh_from_db()
        assert customer.current_balance == Decimal("200.00")

        client.post(f"/api/v1/invoices/{invoice_id}/cancel/")
        customer.refresh_from_db()
        assert customer.current_balance == Decimal("0.00")
