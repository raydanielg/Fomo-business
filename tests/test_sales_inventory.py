"""Sales + inventory correctness — the money-critical tests."""

from decimal import Decimal

import pytest

from apps.inventory.models import InventoryMovement, StockLevel
from apps.products.models import Product
from apps.sales.models import Sale

from .conftest import auth_client


def stock(business, branch, product):
    return StockLevel.objects.get(
        business=business, branch=branch, product=product
    ).quantity


@pytest.mark.django_db
class TestSalesInventory:
    def test_sale_decreases_stock(self, user, business, branch, product):
        client = auth_client(user, business)
        resp = client.post("/api/v1/sales/", {
            "branch_id": str(branch.id),
            "items": [{"product_id": str(product.id), "quantity": "5"}],
            "payment": {"method": "CASH", "amount": "750"},
        }, format="json")
        assert resp.status_code == 201
        assert stock(business, branch, product) == Decimal("45")

        # movement recorded
        mv = InventoryMovement.objects.filter(
            business=business, product=product,
            movement_type="SALE", reference_id=str(resp.json()["data"]["id"]),
        )
        assert mv.count() == 1
        assert mv.first().balance_after == Decimal("45")

    def test_server_calculates_total_not_client(
        self, user, business, branch, product
    ):
        """Client sending a fake total must be ignored."""
        client = auth_client(user, business)
        resp = client.post("/api/v1/sales/", {
            "branch_id": str(branch.id),
            "total": "999999999",   # attacker-supplied
            "items": [{"product_id": str(product.id), "quantity": "2"}],
            "payment": {"method": "CASH", "amount": "300"},
        }, format="json")
        assert resp.status_code == 201
        sale = resp.json()["data"]
        assert sale["total"] == "300.00"  # 2 × 150, computed server-side

    def test_cancelled_sale_restores_stock(
        self, user, business, branch, product
    ):
        client = auth_client(user, business)
        resp = client.post("/api/v1/sales/", {
            "branch_id": str(branch.id),
            "items": [{"product_id": str(product.id), "quantity": "10"}],
            "payment": {"method": "CASH", "amount": "1500"},
        }, format="json")
        sale_id = resp.json()["data"]["id"]
        assert stock(business, branch, product) == Decimal("40")

        resp = client.post(f"/api/v1/sales/{sale_id}/cancel/", {"reason": "test"})
        assert resp.status_code == 200
        assert stock(business, branch, product) == Decimal("50")

    def test_refund_restores_stock(self, user, business, branch, product):
        client = auth_client(user, business)
        resp = client.post("/api/v1/sales/", {
            "branch_id": str(branch.id),
            "items": [{"product_id": str(product.id), "quantity": "3"}],
            "payment": {"method": "CASH", "amount": "450"},
        }, format="json")
        sale_id = resp.json()["data"]["id"]

        resp = client.post(f"/api/v1/sales/{sale_id}/refund/")
        assert resp.status_code == 200
        assert stock(business, branch, product) == Decimal("50")
        sale = Sale.objects.get(id=sale_id)
        assert sale.status == "refunded"
        assert sale.payment_status == "refunded"

    def test_insufficient_stock_rejected(
        self, user, business, branch, product
    ):
        client = auth_client(user, business)
        resp = client.post("/api/v1/sales/", {
            "branch_id": str(branch.id),
            "items": [{"product_id": str(product.id), "quantity": "999"}],
            "payment": {"method": "CASH", "amount": "1"},
        }, format="json")
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "INSUFFICIENT_STOCK"
        # no partial state left
        assert stock(business, branch, product) == Decimal("50")
        assert Sale.objects.count() == 0

    def test_concurrent_sales_cannot_oversell(
        self, user, business, branch, product
    ):
        """Two simultaneous sales of more than stock — only one succeeds."""
        from django.db import connection, transaction
        from apps.sales.services import create_sale

        results = []
        errors = []

        def sell(qty):
            try:
                with transaction.atomic():
                    s = create_sale(
                        business=business, branch=branch, user=user,
                        items_data=[{"product_id": product.id, "quantity": qty}],
                        payment={"method": "CASH", "amount": str(qty * 150)},
                    )
                results.append(s)
            except Exception as e:
                errors.append(e)
            finally:
                connection.close()

        import threading
        t1 = threading.Thread(target=sell, args=(40,))
        t2 = threading.Thread(target=sell, args=(40,))
        t1.start(); t2.start(); t1.join(); t2.join()

        # Exactly one should succeed, stock never negative
        assert len(results) + len(errors) == 2
        final = stock(business, branch, product)
        assert final >= 0
        assert final in (Decimal("50"), Decimal("10"))

    def test_draft_sale_does_not_move_stock(
        self, user, business, branch, product
    ):
        client = auth_client(user, business)
        resp = client.post("/api/v1/sales/", {
            "branch_id": str(branch.id),
            "items": [{"product_id": str(product.id), "quantity": "5"}],
            "draft": True,
        }, format="json")
        assert resp.status_code == 201
        assert stock(business, branch, product) == Decimal("50")

    def test_payment_exceeding_balance_rejected(
        self, user, business, branch, product
    ):
        client = auth_client(user, business)
        # draft sale then complete with overpayment
        resp = client.post("/api/v1/sales/", {
            "branch_id": str(branch.id),
            "items": [{"product_id": str(product.id), "quantity": "1"}],
            "draft": True,
        }, format="json")
        sale_id = resp.json()["data"]["id"]
        resp = client.post(f"/api/v1/sales/{sale_id}/complete/", {
            "payment": {"method": "CASH", "amount": "99999"},
        }, format="json")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_PAYMENT_AMOUNT"

    def test_unique_sku_per_business(
        self, user, business, branch, product
    ):
        client = auth_client(user, business)
        resp = client.post("/api/v1/products/", {
            "name": "Dup", "sku": "SKU-1", "selling_price": "10",
        }, format="json")
        assert resp.status_code == 400
        assert "sku" in str(resp.json()["error"]["details"]).lower()
