from django.http import HttpResponse
from rest_framework import serializers, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import APIError, ErrorCode
from apps.common.mixins import TenantScopedQuerySetMixin
from apps.common.permissions import HasActiveMembership, HasPermission
from apps.subscriptions.services import get_subscription

from .entitlements import EntitlementService, Reason
from .models import Report, ScheduledReport
from .serializers import (
    ReportSerializer,
    ScheduledReportPatchSerializer,
    ScheduledReportSerializer,
    ScheduledReportWriteSerializer,
)
from . import services


def _deny(decision):
    services.raise_for_decision(decision)


class DashboardView(APIView):
    """Home-screen business-wide metrics.

    Members scoped to OWN records (e.g. cashiers) never see whole-business
    figures — dashboard needs reports.view AND a scope above OWN.
    """

    permission_classes = [HasActiveMembership, HasPermission]
    required_permission = "reports.view"
    serializer_class = serializers.Serializer

    def get(self, request):
        if EntitlementService.data_scope(request.membership) == "OWN":
            raise APIError(
                "You do not have permission for this report.",
                code=ErrorCode.PERMISSION_DENIED, status_code=403,
            )
        from .selectors import dashboard

        return Response(
            {"success": True, "data": dashboard(request.business, request)}
        )


class ReportCatalogView(APIView):
    """List every report with this member's access + capabilities."""

    permission_classes = [HasActiveMembership, HasPermission]
    required_permission = "reports.view"
    serializer_class = serializers.Serializer

    def get(self, request):
        data = services.catalog_for(
            request.user, request.business, request.membership
        )
        return Response({"success": True, "data": data})


class ReportAnalyticsView(APIView):
    permission_classes = [HasActiveMembership, HasPermission]
    required_permission = "reports.view"
    serializer_class = serializers.Serializer

    def get(self, request):
        return Response(
            {"success": True, "data": services.usage_analytics(request.business)}
        )


class ReportView(APIView):
    """GET /reports/{key}/ → render the report (entitlement + scope enforced)."""

    permission_classes = [HasActiveMembership]
    serializer_class = serializers.Serializer

    def get(self, request, report_key):
        payload = services.render(request, report_key)
        report = payload["report"]
        return Response(
            {
                "success": True,
                "data": {
                    "report": ReportSerializer(report).data,
                    "result": payload["result"],
                    "scope": payload["scope"],
                    "capabilities": EntitlementService.allowed_capabilities(
                        request.user, request.business, report_key,
                        membership=request.membership,
                    ),
                },
            }
        )


class ReportCapabilitiesView(APIView):
    permission_classes = [HasActiveMembership]
    serializer_class = serializers.Serializer

    def get(self, request, report_key):
        report = Report.objects.filter(key=report_key, is_active=True).first()
        if report is None:
            raise APIError("Report not found.", code=ErrorCode.NOT_FOUND,
                           status_code=404)
        payload = services.report_access_payload(
            request.user, request.business, report,
            membership=request.membership,
        )
        return Response({"success": True, "data": payload})


class ReportFiltersView(APIView):
    """Filters the member may actually use: report-supported ∧ plan-entitled."""

    permission_classes = [HasActiveMembership]
    serializer_class = serializers.Serializer

    def get(self, request, report_key):
        report = Report.objects.filter(key=report_key, is_active=True).first()
        if report is None:
            raise APIError("Report not found.", code=ErrorCode.NOT_FOUND,
                           status_code=404)
        decision = EntitlementService.can_access_report(
            request.user, request.business, report_key,
            membership=request.membership,
        )
        if not decision.allowed:
            return Response(
                {"success": True, "data": {
                    "report": report_key,
                    "access": decision.to_dict(),
                    "filters": [],
                }}
            )

        supported = list(report.supported_filters or [])
        # premium filters need the advanced_filters entitlement
        premium = {"compare", "group_by", "period"}
        if premium & set(supported):
            adv = EntitlementService.check_feature(
                request.business, "reports.advanced_filters",
                user=request.user,
            )
            if not adv.allowed:
                supported = [f for f in supported if f not in premium]

        return Response(
            {"success": True, "data": {
                "report": report_key,
                "access": {"allowed": True},
                "filters": supported,
            }}
        )


class ReportExportView(APIView):
    permission_classes = [HasActiveMembership]
    serializer_class = serializers.Serializer

    def post(self, request, report_key):
        fmt = (request.data.get("format") or "csv").lower()
        if fmt not in ("csv", "xlsx", "pdf"):
            raise APIError("Unsupported format.", code=ErrorCode.VALIDATION_ERROR)
        payload, content_type, filename = services.export(
            request, report_key, fmt
        )
        response = HttpResponse(payload, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class ScheduledReportViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    queryset = ScheduledReport.objects.none()
    permission_classes = [HasActiveMembership, HasPermission]
    permission_map = {
        "list": "reports.view",
        "retrieve": "reports.view",
        "create": "reports.schedule",
        "update": "reports.schedule",
        "partial_update": "reports.schedule",
        "destroy": "reports.schedule",
    }
    filterset_fields = ["status", "report", "frequency"]
    ordering_fields = ["next_run_at", "created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return ScheduledReportWriteSerializer
        if self.action in ("update", "partial_update"):
            return ScheduledReportPatchSerializer
        return ScheduledReportSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ScheduledReport.objects.none()
        qs = ScheduledReport.objects.filter(
            business=self.request.business
        ).select_related("report", "branch", "creator").prefetch_related("recipients")
        # members only see schedules they created, owners/managers see all
        if not (
            self.request.membership.is_owner
            or self.request.membership.has_permission("reports.schedule")
        ):
            qs = qs.filter(creator=self.request.user)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sched = services.create_scheduled(request, serializer.validated_data)
        return Response(
            {"success": True,
             "data": ScheduledReportSerializer(sched).data},
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        sched = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "recipient_ids" in data:
            recipients = services.validate_recipients(
                request.business, data["recipient_ids"], report=sched.report
            )
            sched.recipients.set(recipients)
        for field in ("frequency", "day_of_week", "day_of_month", "hour",
                      "status", "filters"):
            if field in data:
                setattr(sched, field, data[field])
        sched.next_run_at = sched.compute_next_run()
        sched.save()
        return Response(
            {"success": True, "data": ScheduledReportSerializer(sched).data}
        )

    def destroy(self, request, *args, **kwargs):
        sched = self.get_object()
        sched.status = ScheduledReport.Status.DISABLED
        sched.save(update_fields=["status"])
        return Response({"success": True, "message": "Schedule disabled."})
