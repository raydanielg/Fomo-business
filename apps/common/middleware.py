import logging
import uuid

from django.utils.deprecation import MiddlewareMixin

from .context import clear_context, set_current_business, set_current_membership

logger = logging.getLogger("fomo.request")


class RequestIDMiddleware(MiddlewareMixin):
    """Attach a correlation/request ID to every request and response."""

    def process_request(self, request):
        request.id = request.META.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex
        request.META["request_id"] = request.id

    def process_response(self, request, response):
        request_id = getattr(request, "id", None)
        if request_id:
            response["X-Request-ID"] = request_id
        return response


class CurrentBusinessMiddleware(MiddlewareMixin):
    """
    Resolve the tenant (Business) for the request.

    The business is identified by the `X-Business-ID` header. We never trust
    the value blindly — we verify the authenticated user holds an active
    Membership for that business. The resolved business + membership are
    stored on the request and in contextvars for the service layer.
    """

    def process_request(self, request):
        clear_context()
        request.business = None
        request.membership = None

        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            # DRF's JWTAuthentication runs inside the view — we need the user
            # earlier to resolve tenant context, so authenticate here too.
            try:
                from rest_framework_simplejwt.authentication import (
                    JWTAuthentication,
                )

                result = JWTAuthentication().authenticate(request)
                if result:
                    user, _token = result
                    request.user = user
            except Exception:
                user = None

        if not (user and user.is_authenticated):
            return

        business_id = request.META.get("HTTP_X_BUSINESS_ID")
        if not business_id:
            return

        # Lazy import to avoid app-loading circularity
        from apps.memberships.models import Membership

        membership = (
            Membership.objects.select_related("business", "role")
            .filter(
                user=user,
                business_id=business_id,
                status=Membership.Status.ACTIVE,
                business__status="active",
            )
            .first()
        )
        if membership is None:
            return

        request.business = membership.business
        request.membership = membership
        set_current_business(membership.business)
        set_current_membership(membership)

    def process_response(self, request, response):
        clear_context()
        return response


class AuditContextMiddleware(MiddlewareMixin):
    """Capture request metadata (ip, user agent, request id) for audit logging."""

    def process_request(self, request):
        from apps.audit.context import set_audit_context

        ip = self._client_ip(request)
        set_audit_context(
            ip_address=ip,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
            request_id=getattr(request, "id", None),
        )

    @staticmethod
    def _client_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
