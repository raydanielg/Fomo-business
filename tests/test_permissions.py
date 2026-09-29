import pytest

from .conftest import auth_client


@pytest.mark.django_db
class TestPermissions:
    def test_cashier_can_create_sale(
        self, business, branch, product, cashier_membership
    ):
        client = auth_client(cashier_membership.user, business)
        resp = client.post("/api/v1/sales/", {
            "branch_id": str(branch.id),
            "items": [{"product_id": str(product.id), "quantity": "1"}],
            "payment": {"method": "CASH", "amount": "150"},
        }, format="json")
        assert resp.status_code == 201

    def test_cashier_cannot_create_product(
        self, business, cashier_membership
    ):
        client = auth_client(cashier_membership.user, business)
        resp = client.post("/api/v1/products/", {
            "name": "Forbidden", "selling_price": "10",
        }, format="json")
        assert resp.status_code == 403

    def test_cashier_cannot_invite_staff(
        self, business, cashier_membership
    ):
        role_id = str(cashier_membership.role_id)
        client = auth_client(cashier_membership.user, business)
        resp = client.post("/api/v1/memberships/staff/invite/", {
            "email": "someone@x.test", "role_id": role_id,
        }, format="json")
        assert resp.status_code == 403

    def test_cashier_cannot_view_audit(self, business, cashier_membership):
        client = auth_client(cashier_membership.user, business)
        resp = client.get("/api/v1/audit/")
        assert resp.status_code == 403

    def test_owner_can_do_everything(self, user, business):
        client = auth_client(user, business)
        assert client.get("/api/v1/audit/").status_code == 200
        assert client.post("/api/v1/products/", {
            "name": "OK", "selling_price": "10",
        }, format="json").status_code == 201
