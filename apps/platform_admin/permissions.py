from rest_framework import permissions


class IsPlatformAdmin(permissions.BasePermission):
    """Platform-level admin — Django staff/superuser only.

    Business-scoped roles (OWNER, MANAGER, ...) do NOT grant access here;
    platform admin is a distinct trust level.
    """

    message = "Platform administrator access required."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_staff or u.is_superuser))
