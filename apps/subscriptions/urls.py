from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BillingStatusView,
    ChangePlanView,
    CurrentSubscriptionView,
    PlanViewSet,
    SubscriptionCheckoutView,
    UsageView,
)

router = DefaultRouter()
router.register("plans", PlanViewSet, basename="plan")

urlpatterns = [
    path("current/", CurrentSubscriptionView.as_view(), name="subscription-current"),
    path("change-plan/", ChangePlanView.as_view(), name="subscription-change-plan"),
    path("checkout/", SubscriptionCheckoutView.as_view(), name="subscription-checkout"),
    path("billing/<str:reference>/", BillingStatusView.as_view(), name="subscription-billing-status"),
    path("usage/", UsageView.as_view(), name="subscription-usage"),
    path("", include(router.urls)),
]
