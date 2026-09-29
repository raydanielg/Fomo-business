"""Report catalog + feature catalog — seeded into DB, editable in admin.

Keys are stable identifiers; names/descriptions are display-only.
"""

FEATURES = [
    # key, name, category, type, description
    ("reports.sales", "Sales Reports", "REPORTS", "BOOLEAN",
     "Access to sales reports."),
    ("reports.inventory", "Inventory Reports", "REPORTS", "BOOLEAN",
     "Access to inventory reports."),
    ("reports.expenses", "Expense Reports", "REPORTS", "BOOLEAN",
     "Access to expense reports."),
    ("reports.customers", "Customer Reports", "REPORTS", "BOOLEAN",
     "Access to customer reports."),
    ("reports.suppliers", "Supplier Reports", "REPORTS", "BOOLEAN",
     "Access to supplier reports."),
    ("reports.profit", "Profit Reports", "REPORTS", "BOOLEAN",
     "Access to profit/margin reports."),
    ("reports.payments", "Payment Reports", "REPORTS", "BOOLEAN",
     "Access to payment reports."),
    ("reports.staff", "Staff Reports", "REPORTS", "BOOLEAN",
     "Access to staff performance reports."),
    ("reports.branches", "Branch Reports", "REPORTS", "BOOLEAN",
     "Access to per-branch reports."),
    ("reports.tax", "Tax Reports", "FINANCE", "BOOLEAN",
     "Access to tax summary reports."),
    ("reports.advanced_analytics", "Advanced Analytics", "ANALYTICS", "BOOLEAN",
     "Trends, comparisons and advanced analytics reports."),
    ("reports.export", "Report Export", "EXPORTS", "CONFIGURED",
     "Export reports to files. Config: formats, max_exports_per_month, "
     "max_rows_per_export."),
    ("reports.scheduled", "Scheduled Reports", "REPORTS", "CONFIGURED",
     "Schedule recurring reports. Config: max_scheduled_reports."),
    ("reports.comparison", "Report Comparisons", "ANALYTICS", "BOOLEAN",
     "Compare periods inside reports."),
    ("reports.advanced_filters", "Advanced Filters", "REPORTS", "BOOLEAN",
     "Grouping, segmentation and custom comparisons in reports."),
    ("reports.share", "Report Sharing", "REPORTS", "BOOLEAN",
     "Share reports via signed, expiring links."),
    ("reports.custom", "Custom Reports", "REPORTS", "BOOLEAN",
     "Build custom reports."),
    # legacy/general features kept as catalog entries
    ("multi_branch", "Multiple Branches", "BRANCHES", "BOOLEAN",
     "Operate more than one branch."),
    ("api_access", "API Access", "INTEGRATIONS", "BOOLEAN",
     "Programmatic API access."),
    ("receipt_pdf", "PDF Receipts", "SALES", "BOOLEAN",
     "Generate PDF receipts."),
    ("advanced_reports", "Advanced Reports", "REPORTS", "BOOLEAN",
     "Legacy flag — profit/tax family reports."),
]

# Report definitions: key → (name, category, feature_key, capabilities, filters)
_BASIC_FILTERS = ["start_date", "end_date"]
_ADV_FILTERS = ["branch", "staff", "product", "category", "customer",
                "supplier", "payment_method", "status"]
_PREMIUM_FILTERS = ["compare", "group_by", "period"]

REPORTS = [
    # -- sales ---------------------------------------------------------
    ("sales.summary", "Sales Summary", "sales", "reports.sales",
     ["view", "filter", "export", "print", "compare"],
     _BASIC_FILTERS + ["branch", "payment_method", "customer", "staff"]),
    ("sales.detailed", "Detailed Sales", "sales", "reports.sales",
     ["view", "filter", "export", "print"],
     _BASIC_FILTERS + _ADV_FILTERS),
    ("sales.by_product", "Sales by Product", "sales", "reports.sales",
     ["view", "filter", "export", "compare"],
     _BASIC_FILTERS + ["branch", "category", "product"]),
    ("sales.by_customer", "Sales by Customer", "sales", "reports.sales",
     ["view", "filter", "export"], _BASIC_FILTERS + ["branch", "customer"]),
    ("sales.by_staff", "Sales by Staff", "sales", "reports.sales",
     ["view", "filter", "export"], _BASIC_FILTERS + ["branch", "staff"]),
    # -- inventory ------------------------------------------------------
    ("inventory.summary", "Inventory Summary", "inventory", "reports.inventory",
     ["view", "filter"], _BASIC_FILTERS + ["branch"]),
    ("inventory.valuation", "Stock Valuation", "inventory", "reports.inventory",
     ["view", "filter", "export", "print"], ["branch"]),
    ("inventory.movement", "Stock Movements", "inventory", "reports.inventory",
     ["view", "filter", "export"],
     _BASIC_FILTERS + ["branch", "product", "movement_type"]),
    ("inventory.low_stock", "Low Stock", "inventory", "reports.inventory",
     ["view", "filter", "export"], ["branch"]),
    # -- expenses --------------------------------------------------------
    ("expenses.summary", "Expense Summary", "expenses", "reports.expenses",
     ["view", "filter", "export", "print"], _BASIC_FILTERS + ["branch", "payment_method"]),
    ("expenses.by_category", "Expenses by Category", "expenses", "reports.expenses",
     ["view", "filter", "export"], _BASIC_FILTERS + ["branch", "category"]),
    # -- customers --------------------------------------------------------
    ("customers.summary", "Customer Summary", "customers", "reports.customers",
     ["view", "filter", "export"], _BASIC_FILTERS),
    ("customers.purchase_history", "Customer Purchase History", "customers",
     "reports.customers", ["view", "filter", "export"],
     _BASIC_FILTERS + ["customer"]),
    ("customers.outstanding_balances", "Outstanding Balances", "customers",
     "reports.customers", ["view", "filter", "export"], []),
    # -- profit -----------------------------------------------------------
    ("profit.summary", "Profit Summary", "profit", "reports.profit",
     ["view", "filter", "export", "compare"], _BASIC_FILTERS + ["branch"]),
    ("profit.by_product", "Profit by Product", "profit", "reports.profit",
     ["view", "filter", "export", "compare"], _BASIC_FILTERS + ["branch", "product"]),
    ("profit.by_branch", "Profit by Branch", "profit", "reports.profit",
     ["view", "filter", "export", "compare"], _BASIC_FILTERS),
    # -- payments ----------------------------------------------------------
    ("payments.summary", "Payments Summary", "payments", "reports.payments",
     ["view", "filter", "export"], _BASIC_FILTERS + ["branch", "payment_method"]),
    ("payments.by_method", "Payments by Method", "payments", "reports.payments",
     ["view", "filter", "export"], _BASIC_FILTERS + ["branch"]),
    # -- staff --------------------------------------------------------------
    ("staff.performance", "Staff Performance", "staff", "reports.staff",
     ["view", "filter", "export"], _BASIC_FILTERS + ["branch", "staff"]),
    # -- branches -------------------------------------------------------------
    ("branches.performance", "Branch Performance", "branches", "reports.branches",
     ["view", "filter", "export", "compare"], _BASIC_FILTERS),
    # -- suppliers -------------------------------------------------------------
    ("suppliers.summary", "Supplier Summary", "suppliers", "reports.suppliers",
     ["view", "filter", "export"], _BASIC_FILTERS),
    # -- tax -------------------------------------------------------------------
    ("tax.summary", "Tax Summary", "tax", "reports.tax",
     ["view", "filter", "export"], _BASIC_FILTERS + ["branch"]),
    # -- advanced ---------------------------------------------------------------
    ("advanced.sales_trends", "Sales Trends", "advanced", "reports.advanced_analytics",
     ["view", "filter", "export", "compare"], _BASIC_FILTERS + _PREMIUM_FILTERS),
    ("advanced.profit_trends", "Profit Trends", "advanced", "reports.advanced_analytics",
     ["view", "filter", "export", "compare"], _BASIC_FILTERS + _PREMIUM_FILTERS),
    ("advanced.business_comparison", "Business Comparison", "advanced",
     "reports.advanced_analytics",
     ["view", "filter", "compare"], _BASIC_FILTERS + ["branch", "period"]),
]


def seed_report_catalog():
    """Idempotent — creates Features and Reports from the definitions above."""
    from apps.subscriptions.models import Feature

    from .models import Report

    for key, name, category, ftype, desc in FEATURES:
        Feature.objects.update_or_create(
            key=key,
            defaults={
                "name": name, "category": category,
                "feature_type": ftype, "description": desc,
            },
        )
    for i, (key, name, cat, fkey, caps, filters) in enumerate(REPORTS):
        Report.objects.update_or_create(
            key=key,
            defaults={
                "name": name, "category": cat, "feature_key": fkey,
                "capabilities": caps, "supported_filters": filters,
                "sort_order": i,
            },
        )
