"""Tenant isolation — the most critical suite."""

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.customers.models import Customer
from apps.products.models import Product

from .conftest import auth_client


@pytest.mark.django_db
class TestTenantIsolation:
    def test_business_a_cannot_list_business_b_products(
        self, user, user_b, business, business_b, product
    ):
        # product belongs to business A. User B accessing with B context sees nothing.
        client_b = auth_client(user_b, business_b)
        resp = client_b.get("/api/v1/products/")
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] == 0

    def test_business_a_cannot_retrieve_business_b_product(
        self, user, user_b, business, business_b, product
    ):
        client_b = auth_client(user_b, business_b)
        resp = client_b.get(f"/api/v1/products/{product.id}/")
        assert resp.status_code == 404

    def test_business_id_header_is_verified(self, user, business, business_b, product):
        """User A cannot access B's data even by sending B's business id."""
        client = auth_client(user, business_b)  # user is NOT a member of B
        resp = client.get("/api/v1/products/")
        assert resp.status_code == 400  # BUSINESS_REQUIRED (membership not resolved)

    def test_no_business_header_is_rejected(self, user):
        client = auth_client(user)  # no X-Business-ID
        resp = client.get("/api/v1/products/")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "BUSINESS_REQUIRED"

    def test_unauthenticated_is_rejected(self, api_client):
        resp = api_client.get("/api/v1/products/")
        assert resp.status_code == 401

    def test_membership_context_works(self, user, business, product):
        client = auth_client(user, business)
        resp = client.get("/api/v1/products/")
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] == 1
