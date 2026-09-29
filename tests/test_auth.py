import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User

from .conftest import auth_client


@pytest.mark.django_db
class TestAuth:
    def test_register(self, api_client):
        resp = api_client.post("/api/v1/auth/register/", {
            "email": "new@user.test", "password": "Str0ng!Pass",
            "password_confirm": "Str0ng!Pass", "first_name": "New",
        })
        assert resp.status_code == 201
        assert resp.json()["success"] is True
        assert User.objects.filter(email="new@user.test").exists()

    def test_register_duplicate_email(self, api_client, user):
        resp = api_client.post("/api/v1/auth/register/", {
            "email": "owner@a.test", "password": "Str0ng!Pass",
            "password_confirm": "Str0ng!Pass",
        })
        assert resp.status_code == 400
        assert resp.json()["success"] is False

    def test_login(self, api_client, user):
        resp = api_client.post("/api/v1/auth/login/", {
            "email": "owner@a.test", "password": "Passw0rd!x",
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "access" in data and "refresh" in data
        assert data["user"]["email"] == "owner@a.test"

    def test_login_invalid_credentials(self, api_client):
        resp = api_client.post("/api/v1/auth/login/", {
            "email": "x@x.test", "password": "wrong",
        })
        assert resp.status_code == 400

    def test_me(self, user):
        client = auth_client(user)
        resp = client.get("/api/v1/auth/me/")
        assert resp.status_code == 200
        assert resp.json()["data"]["email"] == "owner@a.test"

    def test_logout_blacklists_refresh(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken

        client = APIClient()
        refresh = RefreshToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        resp = client.post("/api/v1/auth/logout/", {"refresh": str(refresh)})
        assert resp.status_code == 200
        # using the same refresh should now fail
        resp2 = client.post("/api/v1/auth/refresh/", {"refresh": str(refresh)})
        assert resp2.status_code == 401

    def test_change_password(self, user):
        client = auth_client(user)
        resp = client.post("/api/v1/auth/change-password/", {
            "current_password": "Passw0rd!x",
            "new_password": "NewPass!2024",
            "new_password_confirm": "NewPass!2024",
        })
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.check_password("NewPass!2024")
