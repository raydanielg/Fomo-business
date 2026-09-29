from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MembershipViewSet, MyMembershipViewSet, RoleViewSet

router = DefaultRouter()
router.register("staff", MembershipViewSet, basename="membership")
router.register("roles", RoleViewSet, basename="role")
router.register("mine", MyMembershipViewSet, basename="my-membership")

urlpatterns = [path("", include(router.urls))]
