"""Canonical permission catalog + default role templates.

Permissions are strings `domain.action`. Role.permissions stores a list.
The OWNER role uses the wildcard "*" which grants everything.
"""

ALL_PERMISSIONS = {
    # products
    "products.view", "products.create", "products.update", "products.delete",
    # inventory
    "inventory.view", "inventory.adjust", "inventory.transfer",
    # sales
    "sales.view", "sales.create", "sales.update", "sales.cancel", "sales.refund",
    # purchases
    "purchases.view", "purchases.create", "purchases.update", "purchases.delete",
    # customers
    "customers.view", "customers.create", "customers.update", "customers.delete",
    # suppliers
    "suppliers.view", "suppliers.create", "suppliers.update", "suppliers.delete",
    # expenses
    "expenses.view", "expenses.create", "expenses.update", "expenses.delete",
    # invoices
    "invoices.view", "invoices.create", "invoices.update", "invoices.cancel",
    # payments
    "payments.view", "payments.create", "payments.refund",
    # reports — `reports.view` is the coarse gate; `reports.<category>` is
    # per-catalog granular control
    "reports.view", "reports.export", "reports.schedule",
    "reports.sales", "reports.inventory", "reports.expenses",
    "reports.customers", "reports.suppliers", "reports.profit",
    "reports.payments", "reports.staff", "reports.branches",
    "reports.tax", "reports.advanced",
    # staff
    "staff.view", "staff.invite", "staff.update", "staff.remove",
    # branches
    "branches.view", "branches.create", "branches.update", "branches.delete",
    # settings
    "settings.view", "settings.update",
    # subscriptions
    "subscription.view", "subscription.manage",
    # audit
    "audit.view",
}

ADMIN_PERMISSIONS = ALL_PERMISSIONS - {"subscription.manage"}

REPORT_MANAGER_PERMISSIONS = {
    "reports.view", "reports.export",
    "reports.sales", "reports.inventory", "reports.expenses",
    "reports.customers", "reports.suppliers", "reports.profit",
    "reports.payments", "reports.tax",
}

REPORT_ACCOUNTANT_PERMISSIONS = {
    "reports.view", "reports.export", "reports.schedule",
    "reports.sales", "reports.inventory", "reports.expenses",
    "reports.customers", "reports.suppliers", "reports.profit",
    "reports.payments", "reports.tax",
}

REPORT_CASHIER_PERMISSIONS = {
    "reports.view", "reports.sales", "reports.payments",
}

REPORT_STOREKEEPER_PERMISSIONS = {
    "reports.view", "reports.inventory", "reports.sales",
}

MANAGER_PERMISSIONS = {
    "products.view", "products.create", "products.update",
    "inventory.view", "inventory.adjust", "inventory.transfer",
    "sales.view", "sales.create", "sales.update", "sales.cancel", "sales.refund",
    "purchases.view", "purchases.create", "purchases.update",
    "customers.view", "customers.create", "customers.update",
    "suppliers.view", "suppliers.create", "suppliers.update",
    "expenses.view", "expenses.create", "expenses.update",
    "invoices.view", "invoices.create", "invoices.update",
    "payments.view", "payments.create",
    "staff.view",
    "branches.view",
    "settings.view",
    "subscription.view",
    "audit.view",
    *REPORT_MANAGER_PERMISSIONS,
}

CASHIER_PERMISSIONS = {
    "products.view",
    "sales.view", "sales.create",
    "customers.view", "customers.create", "customers.update",
    "invoices.view", "invoices.create",
    "payments.view", "payments.create",
    *REPORT_CASHIER_PERMISSIONS,
}

STOREKEEPER_PERMISSIONS = {
    "products.view", "products.create", "products.update",
    "inventory.view", "inventory.adjust", "inventory.transfer",
    "purchases.view", "purchases.create", "purchases.update",
    "suppliers.view",
    *REPORT_STOREKEEPER_PERMISSIONS,
}

ACCOUNTANT_PERMISSIONS = {
    "products.view",
    "sales.view",
    "purchases.view",
    "customers.view", "customers.create", "customers.update",
    "suppliers.view", "suppliers.create", "suppliers.update",
    "expenses.view", "expenses.create", "expenses.update", "expenses.delete",
    "invoices.view", "invoices.create", "invoices.update",
    "payments.view", "payments.create",
    "settings.view",
    "subscription.view",
    "audit.view",
    *REPORT_ACCOUNTANT_PERMISSIONS,
}

STAFF_PERMISSIONS = {
    "products.view",
    "sales.view", "sales.create",
    "customers.view",
    "inventory.view",
    "reports.view", "reports.sales",
}

DEFAULT_ROLE_TEMPLATES = {
    "OWNER": ["*"],
    "ADMIN": sorted(ADMIN_PERMISSIONS),
    "MANAGER": sorted(MANAGER_PERMISSIONS),
    "CASHIER": sorted(CASHIER_PERMISSIONS),
    "STOREKEEPER": sorted(STOREKEEPER_PERMISSIONS),
    "ACCOUNTANT": sorted(ACCOUNTANT_PERMISSIONS),
    "STAFF": sorted(STAFF_PERMISSIONS),
}

# Default report data-visibility per role template (Role.report_scope)
DEFAULT_ROLE_SCOPES = {
    "OWNER": "ALL_BUSINESS",
    "ADMIN": "ALL_BUSINESS",
    "MANAGER": "BRANCH",
    "CASHIER": "OWN",
    "STOREKEEPER": "BRANCH",
    "ACCOUNTANT": "ALL_BUSINESS",
    "STAFF": "OWN",
}
