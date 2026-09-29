from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from rest_framework.routers import DefaultRouter

from apps.common.views import (
    HealthCheckView,
    ReadinessCheckView,
    SupportConfigView,
)
from apps.reports.views import ScheduledReportViewSet

scheduled_router = DefaultRouter()
scheduled_router.register(
    "scheduled-reports", ScheduledReportViewSet, basename="scheduled-report"
)

api_v1 = [
    path("auth/", include("apps.accounts.urls")),
    path("businesses/", include("apps.businesses.urls")),
    path("branches/", include("apps.branches.urls")),
    path("memberships/", include("apps.memberships.urls")),
    path("products/", include("apps.products.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("customers/", include("apps.customers.urls")),
    path("suppliers/", include("apps.suppliers.urls")),
    path("sales/", include("apps.sales.urls")),
    path("purchases/", include("apps.purchases.urls")),
    path("expenses/", include("apps.expenses.urls")),
    path("invoices/", include("apps.invoices.urls")),
    path("payments/", include("apps.payments.urls")),
    path("reports/", include("apps.reports.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("subscriptions/", include("apps.subscriptions.urls")),
    path("audit/", include("apps.audit.urls")),
    path("legal/", include("apps.legal.urls")),
    path("help/", include("apps.help.urls")),
    path("support/", SupportConfigView.as_view(), name="support-config"),
    path("", include(scheduled_router.urls)),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", HealthCheckView.as_view(), name="health"),
    path("ready/", ReadinessCheckView.as_view(), name="readiness"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("api/v1/", include(api_v1)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    try:
        import debug_toolbar

        urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    except ImportError:
        pass
