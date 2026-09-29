from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="report-dashboard"),
    path("analytics/", views.ReportAnalyticsView.as_view(), name="report-analytics"),
    # list catalog
    path("", views.ReportCatalogView.as_view(), name="report-catalog"),
    # per-report actions (declared before the generic key pattern)
    path(
        "<str:report_key>/capabilities/",
        views.ReportCapabilitiesView.as_view(),
        name="report-capabilities",
    ),
    path(
        "<str:report_key>/filters/",
        views.ReportFiltersView.as_view(),
        name="report-filters",
    ),
    path(
        "<str:report_key>/export/",
        views.ReportExportView.as_view(),
        name="report-export",
    ),
    # render a report
    path("<str:report_key>/", views.ReportView.as_view(), name="report-render"),
]
