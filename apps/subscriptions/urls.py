from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ChangePlanView, CurrentSubscriptionView, PlanViewSet, UsageView

router = DefaultRouter()
router.register("plans", PlanViewSet, basename="plan")

urlpatterns = [
    path("current/", CurrentSubscriptionView.as_view(), name="subscription-current"),
    path("change-plan/", ChangePlanView.as_view(), name="subscription-change-plan"),
    path("usage/", UsageView.as_view(), name="subscription-usage"),
    path("", include(router.urls)),
]
