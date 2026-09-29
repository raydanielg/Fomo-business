"""EntitlementService — the single decision point for feature/report access.

Authorization = Subscription Entitlement AND User Permission AND Data Scope.
Nothing here trusts client-supplied business/user/branch identifiers.
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal

from django.utils import timezone

from apps.subscriptions.models import Feature, PlanFeature, UsageRecord
from apps.subscriptions.services import get_subscription, get_usage

from .models import EntitlementEvent, Report

logger = logging.getLogger("fomo.entitlements")


class Reason:
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    NOT_MEMBER = "NOT_MEMBER"
    MEMBERSHIP_SUSPENDED = "MEMBERSHIP_SUSPENDED"
    SUBSCRIPTION_INACTIVE = "SUBSCRIPTION_INACTIVE"
    FEATURE_NOT_INCLUDED = "FEATURE_NOT_INCLUDED"
    REPORT_DISABLED = "REPORT_DISABLED"
    REPORT_NOT_FOUND = "REPORT_NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    BRANCH_ACCESS_DENIED = "BRANCH_ACCESS_DENIED"
    LIMIT_REACHED = "LIMIT_REACHED"
    CAPABILITY_NOT_INCLUDED = "CAPABILITY_NOT_INCLUDED"
    FORMAT_NOT_INCLUDED = "FORMAT_NOT_INCLUDED"


@dataclass
class AccessDecision:
    allowed: bool
    reason: str = ""
    feature_key: str = ""
    report_key: str = ""
    upgrade_available: bool = False
    details: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "feature": self.feature_key,
            "report": self.report_key,
            "upgrade_available": self.upgrade_available,
            **({"details": self.details} if self.details else {}),
        }


def _record(event_type, *, business=None, user=None, feature_key="",
            report_key="", reason="", metadata=None):
    try:
        EntitlementEvent.objects.create(
            business=business, user=user, event_type=event_type,
            feature_key=feature_key, report_key=report_key,
            reason=reason, metadata=metadata or {},
        )
    except Exception:  # pragma: no cover
        logger.exception("Failed to record entitlement event")


def _upgrade_available(feature_key):
    """True when any active+public plan entitles this feature."""
    return PlanFeature.objects.filter(
        feature__key=feature_key, enabled=True, feature__is_active=True,
        plan__is_active=True, plan__is_public=True,
    ).exists()


class EntitlementService:
    # ------------------------------------------------------------------
    # Feature entitlements (subscription-level)
    # ------------------------------------------------------------------

    @staticmethod
    def has_feature(business, feature_key) -> bool:
        sub = get_subscription(business)
        if sub is None or not sub.is_active:
            return False
        return sub.plan.has_feature(feature_key)

    @staticmethod
    def get_feature_configuration(business, feature_key) -> dict:
        sub = get_subscription(business)
        if sub is None or not sub.is_active:
            return {}
        pf = PlanFeature.objects.filter(
            plan=sub.plan, feature__key=feature_key, enabled=True,
            feature__is_active=True,
        ).first()
        return pf.configuration if pf else {}

    @staticmethod
    def check_feature(business, feature_key, *, user=None) -> AccessDecision:
        sub = get_subscription(business)
        if sub is None or not sub.is_active:
            _record(EntitlementEvent.EventType.FEATURE_DENIED,
                    business=business, user=user, feature_key=feature_key,
                    reason=Reason.SUBSCRIPTION_INACTIVE)
            return AccessDecision(
                False, Reason.SUBSCRIPTION_INACTIVE, feature_key=feature_key
            )
        if not sub.plan.has_feature(feature_key):
            _record(EntitlementEvent.EventType.FEATURE_DENIED,
                    business=business, user=user, feature_key=feature_key,
                    reason=Reason.FEATURE_NOT_INCLUDED)
            return AccessDecision(
                False, Reason.FEATURE_NOT_INCLUDED, feature_key=feature_key,
                upgrade_available=_upgrade_available(feature_key),
            )
        return AccessDecision(True, feature_key=feature_key)

    # ------------------------------------------------------------------
    # Report access — the full chain
    # ------------------------------------------------------------------

    @classmethod
    def can_access_report(cls, user, business, report_key,
                          *, membership=None) -> AccessDecision:
        from apps.memberships.models import Membership

        report = Report.objects.filter(key=report_key).first()
        if report is None:
            return AccessDecision(False, Reason.REPORT_NOT_FOUND,
                                  report_key=report_key)
        if not report.is_active:
            _record(EntitlementEvent.EventType.ACCESS_DENIED,
                    business=business, user=user, report_key=report_key,
                    reason=Reason.REPORT_DISABLED)
            return AccessDecision(False, Reason.REPORT_DISABLED,
                                  report_key=report_key)

        if user is None or not getattr(user, "is_authenticated", False):
            return AccessDecision(False, Reason.NOT_AUTHENTICATED,
                                  report_key=report_key)

        if membership is None and business is not None:
            membership = (
                Membership.objects.filter(user=user, business=business)
                .select_related("role")
                .first()
            )
        if membership is None:
            return AccessDecision(False, Reason.NOT_MEMBER,
                                  report_key=report_key)
        if membership.status != Membership.Status.ACTIVE:
            _record(EntitlementEvent.EventType.ACCESS_DENIED,
                    business=business, user=user, report_key=report_key,
                    reason=Reason.MEMBERSHIP_SUSPENDED)
            return AccessDecision(False, Reason.MEMBERSHIP_SUSPENDED,
                                  report_key=report_key)

        # 1. Subscription entitlement
        decision = cls.check_feature(business, report.feature_key, user=user)
        if not decision.allowed:
            decision.report_key = report_key
            _record(EntitlementEvent.EventType.ACCESS_DENIED,
                    business=business, user=user, report_key=report_key,
                    feature_key=report.feature_key, reason=decision.reason)
            return decision

        # 2. Role permission — minimum_access_level + granular category perm
        if not cls._role_allows(membership, report):
            _record(EntitlementEvent.EventType.ACCESS_DENIED,
                    business=business, user=user, report_key=report_key,
                    feature_key=report.feature_key,
                    reason=Reason.PERMISSION_DENIED)
            return AccessDecision(False, Reason.PERMISSION_DENIED,
                                  report_key=report_key,
                                  feature_key=report.feature_key)

        return AccessDecision(True, report_key=report_key,
                              feature_key=report.feature_key)

    @staticmethod
    def _role_allows(membership, report) -> bool:
        perms = membership.get_permissions()
        # granular per-category permission — reports.view alone is only the
        # section gate (dashboard/catalog), it does NOT unlock every report
        if "*" not in perms and report.permission_key not in perms:
            return False

        if report.minimum_access_level == Report.MinAccess.OWNER:
            return membership.is_owner
        if report.minimum_access_level == Report.MinAccess.MANAGER:
            return (
                membership.is_owner
                or membership.role.code in ("ADMIN", "MANAGER", "ACCOUNTANT")
                or "settings.update" in perms
            )
        return True

    # ------------------------------------------------------------------
    # Capabilities (view/filter/export/print/schedule/compare/…)
    # ------------------------------------------------------------------

    @classmethod
    def can_use_report_capability(cls, user, business, report_key, capability,
                                  *, membership=None) -> AccessDecision:
        decision = cls.can_access_report(
            user, business, report_key, membership=membership
        )
        if not decision.allowed:
            return decision

        report = Report.objects.get(key=report_key)
        # "schedule" is plan-controlled — any renderable report can be
        # scheduled; the report's own capability list doesn't constrain it
        if capability != Report.Capability.SCHEDULE and (
            capability not in (report.capabilities or [])
        ):
            _record(EntitlementEvent.EventType.ACCESS_DENIED,
                    business=business, user=user, report_key=report_key,
                    reason=Reason.CAPABILITY_NOT_INCLUDED,
                    metadata={"capability": capability})
            return AccessDecision(False, Reason.CAPABILITY_NOT_INCLUDED,
                                  report_key=report_key,
                                  details={"capability": capability})

        # capability also needs its feature entitlement on the plan
        cap_feature = {
            Report.Capability.EXPORT: "reports.export",
            Report.Capability.SCHEDULE: "reports.scheduled",
            Report.Capability.COMPARE: "reports.comparison",
            Report.Capability.SHARE: "reports.share",
            Report.Capability.ADVANCED_FILTERS: "reports.advanced_filters",
        }.get(capability)
        if cap_feature:
            fd = cls.check_feature(business, cap_feature, user=user)
            if not fd.allowed:
                fd.report_key = report_key
                return fd

        # export needs the role's export permission too
        if capability == Report.Capability.EXPORT:
            perms = membership.get_permissions()
            if "*" not in perms and "reports.export" not in perms:
                return AccessDecision(False, Reason.PERMISSION_DENIED,
                                      report_key=report_key,
                                      details={"capability": capability})
        if capability == Report.Capability.SCHEDULE:
            perms = membership.get_permissions()
            if "*" not in perms and "reports.schedule" not in perms:
                return AccessDecision(False, Reason.PERMISSION_DENIED,
                                      report_key=report_key,
                                      details={"capability": capability})
        return AccessDecision(True, report_key=report_key)

    @classmethod
    def allowed_capabilities(cls, user, business, report_key,
                             *, membership=None) -> dict:
        """Every capability of the report → bool. Drives the frontend UI."""
        report = Report.objects.filter(key=report_key).first()
        caps = {}
        if report is None:
            return caps
        # expose every capability so the frontend can show locked controls
        for cap in Report.Capability.values:
            caps[cap] = cls.can_use_report_capability(
                user, business, report_key, cap, membership=membership
            ).allowed
        return caps

    # ------------------------------------------------------------------
    # Export specifics
    # ------------------------------------------------------------------

    @classmethod
    def allowed_export_formats(cls, business) -> list:
        config = cls.get_feature_configuration(business, "reports.export")
        return config.get("formats", [])

    @classmethod
    def check_export(cls, user, business, report_key, fmt,
                     *, membership=None, row_count=0) -> AccessDecision:
        decision = cls.can_use_report_capability(
            user, business, report_key, Report.Capability.EXPORT,
            membership=membership,
        )
        if not decision.allowed:
            return decision

        config = cls.get_feature_configuration(business, "reports.export")
        formats = config.get("formats", [])
        if fmt not in formats:
            _record(EntitlementEvent.EventType.EXPORT_DENIED,
                    business=business, user=user, report_key=report_key,
                    reason=Reason.FORMAT_NOT_INCLUDED,
                    metadata={"format": fmt})
            return AccessDecision(
                False, Reason.FORMAT_NOT_INCLUDED, report_key=report_key,
                upgrade_available=_upgrade_available("reports.export"),
                details={"format": fmt, "allowed_formats": formats},
            )

        max_rows = config.get("max_rows_per_export")
        if max_rows is not None and row_count > int(max_rows):
            _record(EntitlementEvent.EventType.LIMIT_REACHED,
                    business=business, user=user, report_key=report_key,
                    reason=Reason.LIMIT_REACHED,
                    metadata={"max_rows_per_export": max_rows})
            return AccessDecision(
                False, Reason.LIMIT_REACHED, report_key=report_key,
                details={"max_rows_per_export": max_rows},
            )

        max_monthly = config.get("max_exports_per_month")
        if max_monthly is not None:
            used = get_usage(business, UsageRecord.Metric.REPORT_EXPORTS)
            if used >= int(max_monthly):
                _record(EntitlementEvent.EventType.LIMIT_REACHED,
                        business=business, user=user, report_key=report_key,
                        reason=Reason.LIMIT_REACHED,
                        metadata={"max_exports_per_month": max_monthly})
                return AccessDecision(
                    False, Reason.LIMIT_REACHED, report_key=report_key,
                    upgrade_available=_upgrade_available("reports.export"),
                    details={
                        "max_exports_per_month": max_monthly, "used": used
                    },
                )
        return AccessDecision(True, report_key=report_key)

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    @classmethod
    def check_schedule(cls, user, business, report_key,
                       *, membership=None) -> AccessDecision:
        decision = cls.can_use_report_capability(
            user, business, report_key, Report.Capability.SCHEDULE,
            membership=membership,
        )
        if not decision.allowed:
            return decision
        config = cls.get_feature_configuration(business, "reports.scheduled")
        max_sched = config.get("max_scheduled_reports")
        if max_sched is not None:
            from .models import ScheduledReport

            count = ScheduledReport.objects.filter(
                business=business, status=ScheduledReport.Status.ACTIVE
            ).count()
            if count >= int(max_sched):
                _record(EntitlementEvent.EventType.LIMIT_REACHED,
                        business=business, user=user, report_key=report_key,
                        reason=Reason.LIMIT_REACHED,
                        metadata={"max_scheduled_reports": max_sched})
                return AccessDecision(
                    False, Reason.LIMIT_REACHED, report_key=report_key,
                    details={"max_scheduled_reports": max_sched},
                )
        return AccessDecision(True, report_key=report_key)

    # ------------------------------------------------------------------
    # Data scope — OWN / TEAM / BRANCH / ALL_BUSINESS
    # ------------------------------------------------------------------

    @staticmethod
    def data_scope(membership):
        """Effective visibility ceiling for a member's reports."""
        if membership is None:
            return None
        return getattr(membership.role, "report_scope", "OWN")

    @staticmethod
    def allowed_branch_ids(membership):
        """None = all business branches; else an explicit set."""
        if membership is None:
            return set()
        if not membership.allowed_branches.exists():
            return None  # all
        return set(membership.allowed_branches.values_list("id", flat=True))

    @classmethod
    def resolve_scope(cls, membership, requested_branch_ids=None):
        """
        Returns {"user_only": bool, "branch_ids": set|None, "denied": bool}.
        branch_ids=None → all business branches the member may see.
        """
        role_scope = cls.data_scope(membership)
        allowed = cls.allowed_branch_ids(membership)  # set of UUIDs | None

        requested = None
        if requested_branch_ids:
            # normalize str ids → UUID for comparison
            requested = {
                str(b) for b in requested_branch_ids
            }
            allowed_str = {str(b) for b in allowed} if allowed is not None else None
            if allowed_str is not None and not requested <= allowed_str:
                return {"user_only": False, "branch_ids": set(), "denied": True}
            if allowed is not None:
                requested = {b for b in allowed if str(b) in requested}

        if role_scope == "OWN":
            # own records only — branch still constrained to allowed set
            return {
                "user_only": True,
                "branch_ids": requested if requested is not None else allowed,
                "denied": False,
            }

        effective = requested if requested is not None else allowed
        return {"user_only": False, "branch_ids": effective, "denied": False}
