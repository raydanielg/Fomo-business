"""Object-level + tenant-scoped permissions for DRF views."""

from rest_framework import permissions

from .exceptions import BusinessRequiredError


class HasActiveMembership(permissions.BasePermission):
    """Requires request.business + request.membership (set by middleware)."""

    message = "An active business membership is required for this endpoint."

    def has_permission(self, request, view):
        if getattr(request, "business", None) and getattr(
            request, "membership", None
        ):
            return True
        if request.user and request.user.is_authenticated:
            # Raise a domain error rather than a bare 403 so clients get a
            # consistent BUSINESS_REQUIRED envelope.
            raise BusinessRequiredError()
        return False


class HasPermission(permissions.BasePermission):
    """
    Enforce a named permission from the member's role.

    Views declare:  required_permission = "products.create"
    Or per-method:  permission_map = {"GET": "products.view", "POST": "products.create"}
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        required = self._required_permission(request, view)
        if required is None:
            return True
        membership = getattr(request, "membership", None)
        if membership is None:
            return False
        granted = membership.get_permissions()
        if "*" in granted:
            return True
        if isinstance(required, (list, tuple)):
            # any-of semantics for a list of permissions
            return bool(set(required) & granted)
        return required in granted

    @staticmethod
    def _required_permission(request, view):
        perm_map = getattr(view, "permission_map", None)
        if perm_map:
            # actions (create/list/…) trump HTTP methods
            action = getattr(view, "action", None)
            if action and action in perm_map:
                return perm_map[action]
            return perm_map.get(request.method)
        return getattr(view, "required_permission", None)


class IsOwnerOrAdmin(permissions.BasePermission):
    message = "Only owners and admins can perform this action."

    def has_permission(self, request, view):
        membership = getattr(request, "membership", None)
        if membership is None:
            return False
        return membership.is_owner or membership.has_permission("settings.update")
