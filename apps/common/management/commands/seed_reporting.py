"""Seed the reporting/entitlement catalog — Features, Reports, PlanFeatures.

Idempotent: safe to re-run. Also upgrades existing roles with report scopes
and the granular report permissions introduced with the entitlement system.
"""

from django.core.management.base import BaseCommand


# plan → {feature_key: configuration}
DEFAULT_MATRIX = {
    "FREE": {
        "reports.sales": {},
        "reports.inventory": {},
        "receipt_pdf": {},
    },
    "STARTER": {
        "reports.sales": {},
        "reports.inventory": {},
        "reports.expenses": {},
        "reports.customers": {},
        "receipt_pdf": {},
        "reports.export": {
            "formats": ["csv"],
            "max_exports_per_month": 20,
            "max_rows_per_export": 5000,
        },
    },
    "BUSINESS": {
        "reports.sales": {},
        "reports.inventory": {},
        "reports.expenses": {},
        "reports.customers": {},
        "reports.suppliers": {},
        "reports.profit": {},
        "reports.payments": {},
        "reports.staff": {},
        "reports.tax": {},
        "reports.advanced_filters": {},
        "advanced_reports": {},
        "receipt_pdf": {},
        "multi_branch": {},
        "reports.export": {
            "formats": ["csv", "xlsx"],
            "max_exports_per_month": 100,
            "max_rows_per_export": 20000,
        },
    },
    "PRO": {
        "reports.sales": {},
        "reports.inventory": {},
        "reports.expenses": {},
        "reports.customers": {},
        "reports.suppliers": {},
        "reports.profit": {},
        "reports.payments": {},
        "reports.staff": {},
        "reports.tax": {},
        "reports.branches": {},
        "reports.advanced_analytics": {},
        "reports.advanced_filters": {},
        "reports.comparison": {},
        "advanced_reports": {},
        "receipt_pdf": {},
        "multi_branch": {},
        "api_access": {},
        "reports.export": {
            "formats": ["csv", "xlsx", "pdf"],
            "max_exports_per_month": 500,
            "max_rows_per_export": 50000,
        },
        "reports.scheduled": {"max_scheduled_reports": 10},
    },
    "ENTERPRISE": {
        "reports.sales": {},
        "reports.inventory": {},
        "reports.expenses": {},
        "reports.customers": {},
        "reports.suppliers": {},
        "reports.profit": {},
        "reports.payments": {},
        "reports.staff": {},
        "reports.tax": {},
        "reports.branches": {},
        "reports.advanced_analytics": {},
        "reports.advanced_filters": {},
        "reports.comparison": {},
        "reports.custom": {},
        "advanced_reports": {},
        "receipt_pdf": {},
        "multi_branch": {},
        "api_access": {},
        "reports.export": {"formats": ["csv", "xlsx", "pdf"]},
        "reports.scheduled": {},
    },
}


class Command(BaseCommand):
    help = "Seed features, reports and the plan-feature entitlement matrix."

    def handle(self, *args, **options):
        from apps.reports.catalog import seed_report_catalog
        from apps.roles.models import Role
        from apps.roles.permissions import (
            DEFAULT_ROLE_SCOPES,
            REPORT_ACCOUNTANT_PERMISSIONS,
            REPORT_CASHIER_PERMISSIONS,
            REPORT_MANAGER_PERMISSIONS,
            REPORT_STOREKEEPER_PERMISSIONS,
        )
        from apps.subscriptions.models import Feature, Plan, PlanFeature
        from apps.subscriptions.services import seed_default_plans

        seed_default_plans()
        seed_report_catalog()

        features = {f.key: f for f in Feature.objects.all()}
        for plan_code, matrix in DEFAULT_MATRIX.items():
            plan = Plan.objects.filter(code=plan_code).first()
            if plan is None:
                continue
            for key, config in matrix.items():
                feature = features.get(key)
                if feature is None:
                    self.stderr.write(f"  ! unknown feature {key}")
                    continue
                PlanFeature.objects.update_or_create(
                    plan=plan, feature=feature,
                    defaults={"enabled": True, "configuration": config},
                )

        # upgrade existing roles created before the entitlement system
        role_report_perms = {
            "OWNER": None,  # wildcard — nothing to add
            "ADMIN": set(REPORT_MANAGER_PERMISSIONS) | {
                "reports.schedule", "reports.staff", "reports.branches",
                "reports.advanced",
            },
            "MANAGER": REPORT_MANAGER_PERMISSIONS,
            "CASHIER": REPORT_CASHIER_PERMISSIONS,
            "STOREKEEPER": REPORT_STOREKEEPER_PERMISSIONS,
            "ACCOUNTANT": REPORT_ACCOUNTANT_PERMISSIONS,
            "STAFF": {"reports.view", "reports.sales"},
        }
        for role in Role.objects.filter(is_system=True):
            scope = DEFAULT_ROLE_SCOPES.get(role.code)
            updated = []
            if scope and role.report_scope != scope:
                role.report_scope = scope
                updated.append("report_scope")
            extra = role_report_perms.get(role.code)
            if extra and "*" not in role.permissions:
                merged = sorted(set(role.permissions) | set(extra))
                if merged != role.permissions:
                    role.permissions = merged
                    updated.append("permissions")
            if updated:
                role.save(update_fields=updated + ["updated_at"])

        self.stdout.write(self.style.SUCCESS("Reporting catalog seeded."))
