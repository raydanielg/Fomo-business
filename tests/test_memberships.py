import pytest

from apps.accounts.models import User
from apps.memberships.models import Membership
from apps.roles.models import Role

from .conftest import auth_client


@pytest.mark.django_db
class TestMemberships:
    def test_owner_invites_staff(self, user, business):
        role = Role.objects.get(business=business, code="CASHIER")
        client = auth_client(user, business)
        resp = client.post("/api/v1/memberships/staff/invite/", {
            "email": "newstaff@a.test", "role_id": str(role.id),
            "first_name": "Staff",
        }, format="json")
        assert resp.status_code == 201
        assert Membership.objects.filter(
            business=business, user__email="newstaff@a.test",
            status="invited",
        ).exists()

    def test_invited_user_accepts(self, user, business):
        invited = User.objects.create_user(
            email="invited@a.test", password="Passw0rd!x"
        )
        role = Role.objects.get(business=business, code="STAFF")
        membership = Membership.objects.create(
            user=invited, business=business, role=role, status="invited"
        )
        client = auth_client(invited)
        resp = client.post(
            f"/api/v1/memberships/mine/{membership.business_id}/accept/"
        )
        assert resp.status_code == 200
        membership.refresh_from_db()
        assert membership.status == "active"

    def test_owner_cannot_be_removed(self, user, business):
        owner_m = Membership.objects.get(user=user, business=business)
        client = auth_client(user, business)
        resp = client.delete(f"/api/v1/memberships/staff/{owner_m.id}/")
        assert resp.status_code == 403

    def test_removed_member_loses_access(self, user, business):
        staffer = User.objects.create_user(
            email="staff@a.test", password="Passw0rd!x"
        )
        role = Role.objects.get(business=business, code="CASHIER")
        m = Membership.objects.create(
            user=staffer, business=business, role=role, status="active"
        )
        client = auth_client(staffer, business)
        assert client.get("/api/v1/products/").status_code == 200
        m.status = "removed"
        m.save()
        assert client.get("/api/v1/products/").status_code == 400
