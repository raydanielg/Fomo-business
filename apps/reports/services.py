"""ReportService — orchestrates entitlement → scope → render → usage."""

import logging

from django.db.models import Count, Q
from django.utils import timezone

from apps.common.exceptions import APIError, ErrorCode
from apps.subscriptions.models import UsageRecord
from apps.subscriptions.services import increment_usage

from .entitlements import EntitlementService, Reason
from .models import Report, ReportUsage, ScheduledReport
from . import selectors

logger = logging.getLogger("fomo.reports")

# error code → (http_status, api_error_code)
_REASON_MAP = {
    Reason.NOT_AUTHENTICATED: (401, ErrorCode.AUTH_REQUIRED),
    Reason.NOT_MEMBER: (403, ErrorCode.PERMISSION_DENIED),
    Reason.MEMBERSHIP_SUSPENDED: (403, ErrorCode.PERMISSION_DENIED),
    Reason.SUBSCRIPTION_INACTIVE: (402, ErrorCode.SUBSCRIPTION_INACTIVE),
    Reason.FEATURE_NOT_INCLUDED: (402, ErrorCode.FEATURE_NOT_INCLUDED),
    Reason.CAPABILITY_NOT_INCLUDED: (402, ErrorCode.FEATURE_NOT_AVAILABLE),
    Reason.FORMAT_NOT_INCLUDED: (402, ErrorCode.FEATURE_NOT_AVAILABLE),
    Reason.REPORT_DISABLED: (404, ErrorCode.NOT_FOUND),
    Reason.REPORT_NOT_FOUND: (404, ErrorCode.NOT_FOUND),
    Reason.PERMISSION_DENIED: (403, ErrorCode.PERMISSION_DENIED),
    Reason.BRANCH_ACCESS_DENIED: (403, ErrorCode.PERMISSION_DENIED),
    Reason.LIMIT_REACHED: (402, ErrorCode.PLAN_LIMIT_REACHED),
}

_MESSAGES = {
    Reason.NOT_AUTHENTICATED: "Authentication required.",
    Reason.NOT_MEMBER: "You are not a member of this business.",
    Reason.MEMBERSHIP_SUSPENDED: "Your membership is not active.",
    Reason.SUBSCRIPTION_INACTIVE: "The business subscription is not active.",
    Reason.FEATURE_NOT_INCLUDED: "This feature is not included in your plan.",
    Reason.CAPABILITY_NOT_INCLUDED: "This capability is not included in your plan.",
    Reason.FORMAT_NOT_INCLUDED: "This export format is not included in your plan.",
    Reason.REPORT_DISABLED: "This report is not available.",
    Reason.REPORT_NOT_FOUND: "Report not found.",
    Reason.PERMISSION_DENIED: "You do not have permission for this report.",
    Reason.BRANCH_ACCESS_DENIED: "No access to the requested branch.",
    Reason.LIMIT_REACHED: "Plan limit reached.",
}


def raise_for_decision(decision):
    """Convert an AccessDecision into a client-facing APIError."""
    if decision.allowed:
        return
    status, code = _REASON_MAP.get(
        decision.reason, (403, ErrorCode.PERMISSION_DENIED)
    )
    raise APIError(
        _MESSAGES.get(decision.reason, "Access denied."),
        code=code,
        status_code=status,
        details={
            "reason": decision.reason,
            "feature": decision.feature_key,
            "report": decision.report_key,
            "upgrade_available": decision.upgrade_available,
            **decision.details,
        },
    )


def _params(request):
    """Whitelisted report params — dates, ids, segmentation."""
    qp = request.query_params
    keys = [
        "start_date", "end_date", "branch", "staff", "product", "category",
        "customer", "supplier", "payment_method", "status", "movement_type",
        "compare", "group_by", "period",
    ]
    return {k: qp.get(k) for k in keys if qp.get(k) is not None}


def _scope_for(membership, params):
    requested = [params["branch"]] if params.get("branch") else None
    scope = EntitlementService.resolve_scope(
        membership, requested_branch_ids=requested
    )
    scope["user_id"] = str(membership.user_id)
    return scope


def render(request, report_key):
    """Full chain: access → scope → render → usage."""
    business = request.business
    membership = request.membership

    decision = EntitlementService.can_access_report(
        request.user, business, report_key, membership=membership
    )
    raise_for_decision(decision)

    report = Report.objects.get(key=report_key)
    params = _params(request)
    scope = _scope_for(membership, params)
    if scope["denied"]:
        raise_for_decision(type("D", (), {"allowed": False,
                                          "reason": Reason.BRANCH_ACCESS_DENIED,
                                          "feature_key": "",
                                          "report_key": report_key,
                                          "upgrade_available": False,
                                          "details": {}})())

    data = selectors.render_report(report_key, business, scope, params)

    ReportUsage.objects.create(
        business=business, user=request.user,
        report_key=report_key, action=ReportUsage.Action.VIEW,
        metadata={"params": {k: str(v) for k, v in params.items()}},
    )
    return {"report": report, "result": data, "scope": {
        "user_only": scope["user_only"],
        "branch_ids": [str(b) for b in scope["branch_ids"]] if scope["branch_ids"] else None,
    }}


def export(request, report_key, fmt):
    """Entitlement + format + limits, then render rows into a file."""
    business = request.business
    membership = request.membership

    params = _params(request)
    scope = _scope_for(membership, params)
    if scope["denied"]:
        raise APIError(_MESSAGES[Reason.BRANCH_ACCESS_DENIED],
                       code=ErrorCode.PERMISSION_DENIED, status_code=403)

    # two-pass: render first to count rows, then check export limits
    data = selectors.render_report(report_key, business, scope, params)
    if data is None:
        raise APIError("Report not found.", code=ErrorCode.REPORT_NOT_FOUND,
                       status_code=404)
    row_count = len(data["rows"])

    decision = EntitlementService.check_export(
        request.user, business, report_key, fmt,
        membership=membership, row_count=row_count,
    )
    raise_for_decision(decision)

    report = Report.objects.get(key=report_key)
    from .exporters import EXPORTERS

    content_type, fn = EXPORTERS[fmt]
    if fmt == "pdf":
        payload = fn(data["columns"], data["rows"],
                     title=report.name, business_name=business.name)
    else:
        payload = fn(data["columns"], data["rows"])

    increment_usage(business, UsageRecord.Metric.REPORT_EXPORTS)
    ReportUsage.objects.create(
        business=business, user=request.user,
        report_key=report_key, action=ReportUsage.Action.EXPORT,
        format=fmt, row_count=row_count,
    )
    return payload, content_type, f"{report_key}.{fmt}"


def report_access_payload(user, business, report, *, membership=None):
    """The frontend-facing access/capability descriptor for one report."""
    decision = EntitlementService.can_access_report(
        user, business, report.key, membership=membership
    )
    capabilities = (
        EntitlementService.allowed_capabilities(
            user, business, report.key, membership=membership
        )
        if decision.allowed
        else {}
    )
    return {
        "report": {
            "key": report.key,
            "name": report.name,
            "description": report.description,
            "category": report.category,
        },
        "access": decision.to_dict(),
        "capabilities": capabilities,
        "export_formats": (
            EntitlementService.allowed_export_formats(business)
            if capabilities.get("export") else []
        ),
    }


def catalog_for(user, business, membership):
    """All active reports with per-report access — one query set."""
    reports = Report.objects.filter(is_active=True)
    return [
        report_access_payload(user, business, r, membership=membership)
        for r in reports
    ]


def validate_recipients(business, recipient_ids, report=None):
    """Scheduled-report recipients must be active members who are themselves
    entitled to see the report — no shipping profit reports to a cashier who
    lacks the permission."""
    from apps.memberships.models import Membership

    memberships = list(
        Membership.objects.filter(
            business=business, user_id__in=recipient_ids,
            status=Membership.Status.ACTIVE,
        ).select_related("user", "role")
    )
    if len(memberships) != len(set(recipient_ids)):
        raise APIError(
            "One or more recipients are not active members of this business.",
            code=ErrorCode.VALIDATION_ERROR,
        )
    if report is not None:
        for m in memberships:
            decision = EntitlementService.can_access_report(
                m.user, business, report.key, membership=m
            )
            if not decision.allowed:
                raise APIError(
                    f"Recipient {m.user.email} is not entitled to this report.",
                    code=ErrorCode.PERMISSION_DENIED, status_code=403,
                    details={"reason": decision.reason,
                             "recipient": str(m.user_id)},
                )
    return [m.user for m in memberships]


def create_scheduled(request, data):
    business, membership = request.business, request.membership
    report_key = data["report_key"]

    decision = EntitlementService.check_schedule(
        request.user, business, report_key, membership=membership
    )
    raise_for_decision(decision)

    report = Report.objects.get(key=report_key)

    # format must be an entitled export format
    fmt = data.get("format", "csv")
    if fmt not in EntitlementService.allowed_export_formats(business):
        raise APIError(
            f"Format '{fmt}' is not included in your plan.",
            code=ErrorCode.FEATURE_NOT_AVAILABLE, status_code=402,
        )

    # optional branch pin — must be within the creator's scope
    branch = None
    if data.get("branch_id"):
        from apps.branches.models import Branch

        branch = Branch.objects.filter(
            id=data["branch_id"], business=business
        ).first()
        if branch is None:
            raise APIError("Branch not found.", code=ErrorCode.NOT_FOUND,
                           status_code=404)
        if not membership.can_access_branch(branch.id):
            raise APIError("No access to this branch.",
                           code=ErrorCode.PERMISSION_DENIED, status_code=403)

    recipients = validate_recipients(business, data["recipient_ids"],
                                     report=report)

    sched = ScheduledReport.objects.create(
        business=business, report=report, branch=branch,
        creator=request.user,
        frequency=data["frequency"], day_of_week=data.get("day_of_week"),
        day_of_month=data.get("day_of_month"),
        hour=data.get("hour", 8), format=fmt,
        filters=data.get("filters", {}),
    )
    sched.recipients.set(recipients)
    sched.next_run_at = sched.compute_next_run()
    sched.save(update_fields=["next_run_at"])

    ReportUsage.objects.create(
        business=business, user=request.user, report_key=report_key,
        action=ReportUsage.Action.SCHEDULE,
    )
    return sched


def run_scheduled_report(sched):
    """Executed by Celery — validates everything again, renders, emails."""
    business = sched.business
    report = sched.report

    decision = EntitlementService.check_feature(
        business, "reports.scheduled", user=sched.creator
    )
    if not decision.allowed:
        sched.status = ScheduledReport.Status.DISABLED
        sched.save(update_fields=["status"])
        logger.info("Scheduled report %s disabled — feature lost", sched.id)
        return False

    params = dict(sched.filters)
    if sched.branch_id:
        params["branch"] = str(sched.branch_id)
    scope = {"user_only": False,
             "branch_ids": {sched.branch_id} if sched.branch_id else None,
             "user_id": None}
    data = selectors.render_report(report.key, business, scope, params)
    if data is None:
        return False

    from .exporters import EXPORTERS

    content_type, fn = EXPORTERS.get(sched.format, EXPORTERS["csv"])
    payload = fn(data["columns"], data["rows"]) if sched.format != "pdf" else fn(
        data["columns"], data["rows"], title=report.name,
        business_name=business.name,
    )

    # deliver via email provider (attachments supported by the console provider's
    # log line; SMTP-backed providers attach the payload)
    from apps.notifications.providers import get_email_provider

    provider = get_email_provider()
    for user in sched.recipients.all():
        provider.send(
            to=user.email,
            subject=f"Scheduled report: {report.name}",
            message=(
                f"Your scheduled report '{report.name}' for "
                f"{business.name} is attached."
            ),
            attachment=(f"{report.key}.{sched.format}", payload, content_type),
        )

    sched.last_run_at = timezone.now()
    sched.next_run_at = sched.compute_next_run()
    sched.save(update_fields=["last_run_at", "next_run_at"])
    ReportUsage.objects.create(
        business=business, report_key=report.key,
        action=ReportUsage.Action.EXPORT, format=sched.format,
        row_count=len(data["rows"]),
        metadata={"scheduled_report_id": str(sched.id)},
    )
    return True


def usage_analytics(business):
    """Per-business usage — most-used reports, export mix, denials."""
    views = list(
        ReportUsage.objects.filter(
            business=business, action=ReportUsage.Action.VIEW
        )
        .values("report_key")
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    )
    exports = list(
        ReportUsage.objects.filter(
            business=business, action=ReportUsage.Action.EXPORT
        )
        .values("report_key", "format")
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    )
    denials = list(
        ReportUsage.objects.filter(
            business=business, action=ReportUsage.Action.DENIED
        )
        .values("report_key")
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    )
    totals = ReportUsage.objects.filter(business=business).aggregate(
        views=Count("id", filter=Q(action="view")),
        exports=Count("id", filter=Q(action="export")),
    )
    return {
        "most_viewed": views,
        "most_exported": exports,
        "most_denied": denials,
        "totals": totals,
    }
