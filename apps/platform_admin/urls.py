from django.urls import path

from . import views

app_name = "platform_admin"

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("growth/", views.GrowthView.as_view(), name="growth"),
    path("businesses/", views.BusinessesListView.as_view(), name="businesses"),
    path("businesses/<uuid:pk>/", views.BusinessDetailView.as_view(), name="business-detail"),
    path("users/", views.UsersListView.as_view(), name="users"),
    path("users/<uuid:pk>/", views.UserDetailView.as_view(), name="user-detail"),
    path("audit-logs/", views.AuditLogsView.as_view(), name="audit-logs"),
    path("notifications/", views.NotificationsListView.as_view(), name="notifications"),
    path("system-health/", views.SystemHealthView.as_view(), name="system-health"),
    path("activity/", views.ActivityView.as_view(), name="activity"),
    path("plans/", views.PlansView.as_view(), name="plans"),
]
