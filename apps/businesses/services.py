"""BusinessService — tenant provisioning."""

from django.db import transaction

from apps.branches.models import Branch
from apps.memberships.models import Membership
from apps.roles.models import Role
from apps.roles.permissions import DEFAULT_ROLE_SCOPES, DEFAULT_ROLE_TEMPLATES
from apps.subscriptions.services import provision_free_subscription

from .models import Business


def create_business(*, owner, name, **fields):
    """
    Provision a new tenant:
    business → default roles → default branch → owner membership → FREE subscription.
    """
    with transaction.atomic():
        business = Business.objects.create(owner=owner, name=name, **fields)

        roles = {}
        for code, perms in DEFAULT_ROLE_TEMPLATES.items():
            roles[code] = Role.objects.create(
                business=business,
                code=code,
                name=code.title(),
                permissions=perms,
                report_scope=DEFAULT_ROLE_SCOPES.get(code, "OWN"),
                is_system=True,
            )

        branch = Branch.objects.create(
            business=business,
            name="Main Branch",
            code="MAIN",
            is_default=True,
        )

        Membership.objects.create(
            user=owner,
            business=business,
            role=roles["OWNER"],
            status=Membership.Status.ACTIVE,
        )

        provision_free_subscription(business)

    return business
