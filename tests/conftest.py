import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.branches.models import Branch
from apps.businesses.services import create_business
from apps.inventory.services import adjust_stock
from apps.memberships.models import Membership
from apps.products.models import Category, Product, Unit
from apps.roles.models import Role
from apps.subscriptions.services import seed_default_plans


@pytest.fixture(autouse=True, scope="session")
def _seed_plans(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        seed_default_plans()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="owner@a.test", password="Passw0rd!x", is_verified=True,
        first_name="Alice", last_name="Owner",
    )


@pytest.fixture
def user_b(db):
    return User.objects.create_user(
        email="owner@b.test", password="Passw0rd!x", is_verified=True,
    )


@pytest.fixture
def business(user):
    return create_business(owner=user, name="Shop A")


@pytest.fixture
def business_b(user_b):
    return create_business(owner=user_b, name="Shop B")


@pytest.fixture
def branch(business):
    return business.branch_set.get()


@pytest.fixture
def cashier_membership(business, db):
    cashier = User.objects.create_user(email="cashier@a.test", password="Passw0rd!x")
    role = Role.objects.get(business=business, code="CASHIER")
    return Membership.objects.create(
        user=cashier, business=business, role=role,
        status=Membership.Status.ACTIVE,
    )


@pytest.fixture
def product(business, branch, user):
    cat = Category.objects.create(business=business, name="General")
    unit = Unit.objects.create(business=business, name="Pieces", abbreviation="pcs")
    p = Product.objects.create(
        business=business, name="Test Product", sku="SKU-1",
        category=cat, unit=unit,
        buying_price=100, selling_price=150, cost_price=100,
        low_stock_threshold=5,
    )
    adjust_stock(
        business=business, branch=branch, product=p,
        quantity=50, direction="in", user=user,
    )
    return p


def auth_client(user, business=None):
    """Client with JWT + optional business context."""
    from rest_framework_simplejwt.tokens import RefreshToken

    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    if business is not None:
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token.access_token}",
            HTTP_X_BUSINESS_ID=str(business.id),
        )
    return client
