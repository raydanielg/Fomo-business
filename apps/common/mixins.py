"""Shared viewset mixins that enforce tenant scoping.

Views NEVER accept a business_id from the request body/query for scoping —
the business always comes from request.business (resolved + authorized by
CurrentBusinessMiddleware from the user's membership).
"""

from .exceptions import BusinessRequiredError


class TenantScopedQuerySetMixin:
    """Filter all querysets to request.business and inject it on create."""

    def get_queryset(self):
        qs = super().get_queryset()
        business = getattr(self.request, "business", None)
        if business is None:
            raise BusinessRequiredError()
        return qs.filter(business=business)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["business"] = getattr(self.request, "business", None)
        context["membership"] = getattr(self.request, "membership", None)
        return context

    def perform_create(self, serializer):
        business = getattr(self.request, "business", None)
        if business is None:
            raise BusinessRequiredError()
        kwargs = {"business": business}
        membership = getattr(self.request, "membership", None)
        # Models with created_by receive the user automatically
        model = serializer.Meta.model
        if hasattr(model, "created_by") and "created_by" not in serializer.validated_data:
            kwargs["created_by"] = self.request.user
        serializer.save(**kwargs)
