"""Membership services — invitations, role changes, removal."""

import secrets

from django.db import transaction

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.audit.services import log as audit_log
from apps.branches.models import Branch
from apps.common.exceptions import APIError, ErrorCode
from apps.roles.models import Role

from .models import Membership


def invite_member(*, business, email, role_id, invited_by,
                  allowed_branch_ids=None, first_name="", last_name=""):
    email = email.lower()
    role = Role.objects.filter(id=role_id, business=business).first()
    if role is None:
        raise APIError("Invalid role.", code=ErrorCode.VALIDATION_ERROR)

    # Subscription: staff limit
    from apps.subscriptions.services import enforce_limit

    staff_count = Membership.objects.filter(
        business=business, status=Membership.Status.ACTIVE
    ).count()
    enforce_limit(business, "max_staff", current_value=staff_count)

    if role.code == "OWNER":
        raise APIError("Cannot invite an additional owner.",
                       code=ErrorCode.PERMISSION_DENIED, status_code=403)

    branches = []
    if allowed_branch_ids:
        branches = list(
            Branch.objects.filter(id__in=allowed_branch_ids, business=business)
        )
        if len(branches) != len(set(allowed_branch_ids)):
            raise APIError("One or more branches are invalid.",
                           code=ErrorCode.VALIDATION_ERROR)

    with transaction.atomic():
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                # unusable password — user sets it via invite link
            },
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])

        membership, membership_created = Membership.objects.get_or_create(
            user=user,
            business=business,
            defaults={
                "role": role,
                "status": Membership.Status.INVITED,
                "invited_by": invited_by,
            },
        )
        if not membership_created:
            if membership.status == Membership.Status.REMOVED:
                membership.status = Membership.Status.INVITED
                membership.role = role
                membership.invited_by = invited_by
                membership.save(update_fields=["status", "role", "invited_by"])
            else:
                raise APIError(
                    "This user is already a member.",
                    code=ErrorCode.CONFLICT,
                    status_code=409,
                )
        if branches:
            membership.allowed_branches.set(branches)

    audit_log(
        AuditLog.Action.STAFF_INVITED,
        business=business,
        user=invited_by,
        resource_type="Membership",
        resource_id=membership.id,
        new_values={"email": email, "role": role.code},
    )

    # Invite token acts as password-reset token for the new user
    from apps.accounts.models import AuthToken
    from apps.accounts.services import create_auth_token
    from apps.notifications.tasks import send_invite_email

    token = create_auth_token(user, AuthToken.Purpose.PASSWORD_RESET)
    send_invite_email.delay(
        user_id=str(user.id),
        business_name=business.name,
        token=token.token,
        inviter_name=invited_by.full_name,
    )
    return membership


def update_membership(*, membership, actor, role_id=None, status=None,
                      allowed_branch_ids=None):
    business = membership.business

    if membership.is_owner and membership.user == business.owner:
        raise APIError("The business owner cannot be modified.",
                       code=ErrorCode.PERMISSION_DENIED, status_code=403)

    old_values = {
        "role": membership.role.code,
        "status": membership.status,
    }

    with transaction.atomic():
        if role_id is not None:
            role = Role.objects.filter(id=role_id, business=business).first()
            if role is None:
                raise APIError("Invalid role.", code=ErrorCode.VALIDATION_ERROR)
            if role.code == "OWNER":
                raise APIError("Cannot assign the owner role.",
                               code=ErrorCode.PERMISSION_DENIED, status_code=403)
            membership.role = role

        if status is not None:
            if status not in Membership.Status.values:
                raise APIError("Invalid status.", code=ErrorCode.VALIDATION_ERROR)
            membership.status = status

        if allowed_branch_ids is not None:
            branches = list(
                Branch.objects.filter(id__in=allowed_branch_ids, business=business)
            )
            membership.allowed_branches.set(branches)

        membership.save()

    audit_log(
        AuditLog.Action.STAFF_UPDATED,
        business=business,
        user=actor,
        resource_type="Membership",
        resource_id=membership.id,
        old_values=old_values,
        new_values={"role": membership.role.code, "status": membership.status},
    )
    return membership


def remove_membership(*, membership, actor):
    if membership.is_owner and membership.user == membership.business.owner:
        raise APIError("The business owner cannot be removed.",
                       code=ErrorCode.PERMISSION_DENIED, status_code=403)
    membership.status = Membership.Status.REMOVED
    membership.save(update_fields=["status"])
    audit_log(
        AuditLog.Action.STAFF_REMOVED,
        business=membership.business,
        user=actor,
        resource_type="Membership",
        resource_id=membership.id,
    )


def accept_invitation(*, user, business_id):
    """Activate a pending invite for the authenticated user."""
    membership = Membership.objects.filter(
        user=user, business_id=business_id, status=Membership.Status.INVITED
    ).first()
    if membership is None:
        raise APIError("No pending invitation found.",
                       code=ErrorCode.NOT_FOUND, status_code=404)
    membership.activate()
    return membership


def generate_temp_password():
    return secrets.token_urlsafe(12)
