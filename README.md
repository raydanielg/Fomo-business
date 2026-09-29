# Fomo — Backend

> **Your Business, Simplified.**

Multi-tenant SaaS business-management platform built for small and growing
businesses in Tanzania. Sales/POS, inventory, customers, suppliers, expenses,
invoices, payments, staff roles, reports, notifications, and SaaS subscriptions.

## Stack

- Python 3.12 · Django 5 · Django REST Framework
- PostgreSQL · Redis · Celery + Celery Beat
- JWT (access + rotating refresh) via `djangorestframework-simplejwt`
- OpenAPI docs via `drf-spectacular`
- pytest + pytest-django

## Architecture

Modular monolith — each app owns one business domain. Tenant isolation is
enforced at the model layer (every tenant model carries `business`), the
middleware layer (`X-Business-ID` header → verified `Membership`), and the
permission layer (role-based permission strings checked on every endpoint).

```
Business ── Membership ── User
    ├── Branch ── InventoryMovement / StockLevel
    ├── Product ── Sale ── SaleItem ── Payment
    ├── Customer ── Invoice ── InvoiceItem
    ├── Supplier ── Purchase
    ├── Expense
    ├── Subscription ── Plan / UsageRecord
    └── AuditLog
```

Key rules enforced server-side:

- **Never trust the client**: totals, stock, prices are computed from the
  catalog; the `business_id` comes from the verified membership, never the body.
- **Money**: `DecimalField` everywhere, server-side calculation, no floats.
- **Stock**: every change writes an immutable `InventoryMovement` +
  updates `StockLevel` under `select_for_update` inside `transaction.atomic`.
- **Permissions**: role → permission strings (`products.create`, `sales.refund`…)
  enforced in `HasPermission` on every view.
- **Audit**: every sensitive action writes an `AuditLog` (sanitized — never
  passwords/tokens).

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements/development.txt

cp .env.example .env           # fill in DATABASE_URL, SECRET_KEY, …
python manage.py migrate
python manage.py seed_plans    # subscription plan catalog
python manage.py seed_cron     # Celery Beat periodic tasks
python manage.py createsuperuser
python manage.py runserver
```

Workers:

```bash
celery -A config worker -l info
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

Tests:

```bash
pytest                       # sqlite (fast)
TEST_DATABASE_URL=postgres://…  pytest   # against real PostgreSQL
```

Demo data (development only — refuses to run with DEBUG=False):

```bash
python manage.py seed_demo   # owner@demo.fomo / DemoPass123!
```

## API

Base: `/api/v1/` — see `/api/docs/` (Swagger) or `/api/schema/` (OpenAPI YAML).

Every business-scoped request needs:

```
Authorization: Bearer <access_token>
X-Business-ID: <business uuid>
```

The business is resolved from the user's **verified membership** — a header
for a business the user doesn't belong to is rejected, and the tenant can
never be overridden from the request body.

### Response envelope

```jsonc
// success
{"success": true, "data": {…}, "pagination": {"page":1,"page_size":20,"total":100,"pages":5}}

// error
{"success": false, "error": {"code": "INSUFFICIENT_STOCK", "message": "…", "details": {}}, "request_id": "…"}
```

### Endpoint map

| Area | Path | Notes |
|---|---|---|
| Auth | `/api/v1/auth/` | register, login, refresh, logout, me, password reset, email verify, sessions |
| Businesses | `/api/v1/businesses/` | create provisions roles+branch+subscription |
| Staff/Roles | `/api/v1/memberships/staff/`, `/roles/` | invite, accept, role management |
| Branches | `/api/v1/branches/` | per-member branch scoping |
| Products | `/api/v1/products/` (+`/categories/`, `/units/`) | SKU/barcode unique per business |
| Inventory | `/api/v1/inventory/` | `levels`, `movements`, `adjust/`, `transfer/` |
| Customers | `/api/v1/customers/` | `history/`, `payments/` |
| Suppliers | `/api/v1/suppliers/` | `history/` |
| Sales | `/api/v1/sales/` | `complete`, `cancel`, `refund`, `receipt` (PDF) |
| Purchases | `/api/v1/purchases/` | `receive`, `cancel` |
| Invoices | `/api/v1/invoices/` | `issue`, `cancel`, `record-payment` |
| Payments | `/api/v1/payments/` | sale/invoice/customer targets |
| Expenses | `/api/v1/expenses/` (+`/categories/`) | |
| Reports | `/api/v1/reports/` | catalog, `/{key}/`, `/{key}/capabilities/`, `/{key}/filters/`, `/{key}/export/` (csv/xlsx/pdf), `dashboard/`, `analytics/` |
| Scheduled reports | `/api/v1/scheduled-reports/` | create/list/patch/disable — requires `reports.scheduled` |
| Notifications | `/api/v1/notifications/` | `read`, `read-all`, `unread-count` |
| Subscriptions | `/api/v1/subscriptions/` | plans, `plans/comparison/` (full feature matrix), current, change-plan, usage |
| Audit | `/api/v1/audit/` | read-only |

## Entitlement system

Report/feature access = **subscription entitlement AND role permission AND
data scope** — all three, server-side.

- `Feature` + `PlanFeature` rows define what each plan includes (with JSON
  `configuration` for limits like `max_exports_per_month`, export `formats`,
  `max_scheduled_reports`). Plans/features are admin data — no `if plan ==
  "PRO"` anywhere.
- `Report` catalog rows map a report key → required feature, supported
  capabilities and filters.
- `EntitlementService` (`apps/reports/entitlements.py`) is the single
  decision point: `has_feature`, `get_feature_configuration`,
  `can_access_report`, `can_use_report_capability`, `check_export`,
  `check_schedule`, `resolve_scope` — every denial returns a structured
  reason (`FEATURE_NOT_INCLUDED`, `PERMISSION_DENIED`,
  `BRANCH_ACCESS_DENIED`, `LIMIT_REACHED`, …) plus `upgrade_available`.
- `Role.report_scope` (OWN/TEAM/BRANCH/ALL_BUSINESS) + membership
  `allowed_branches` define data visibility; selectors apply it.
- `ReportUsage` tracks view/export/schedule/deny per business;
  `EntitlementEvent` logs denials and plan changes.

Seed/re-seed the catalog:

```bash
python manage.py seed_reporting   # features, reports, plan-feature matrix
```

## Health

`GET /health/` (liveness) · `GET /ready/` (checks DB + Redis)

## Docker

```bash
docker compose up --build   # web + postgres + redis + celery + celery-beat
```

## Environment

See `.env.example`. Secrets come from env only — never hardcoded. In
production: `DEBUG=False`, real `SECRET_KEY`, `JWT_SIGNING_KEY`, SMTP email,
`SENTRY_DSN` optional.

## Project layout

```
backend/
├── config/           # settings (base/dev/prod/test), urls, celery, asgi/wsgi
├── apps/
│   ├── common/       # middleware (request-id, tenant), exceptions,
│   │                 # pagination, envelope renderer, health, seed commands
│   ├── accounts/     # custom User (email login), tokens, device sessions
│   ├── businesses/   # tenant root + provisioning service
│   ├── memberships/  # user↔business link, invites, staff views
│   ├── roles/        # permission catalog + role model
│   ├── branches/
│   ├── products/     # categories, units, products
│   ├── inventory/    # StockLevel + immutable InventoryMovement ledger
│   ├── customers/  suppliers/
│   ├── sales/        # SaleService — atomic sale completion + receipts (PDF)
│   ├── purchases/    # supplier receiving
│   ├── expenses/
│   ├── invoices/     # InvoiceService — unique numbers, lifecycle
│   ├── payments/     # PaymentService — balance-true money movement
│   ├── reports/      # read-only selectors, dashboard
│   ├── notifications/# Notification model + provider registry + tasks
│   ├── subscriptions/# Plan, Subscription, UsageRecord, entitlements
│   └── audit/        # AuditLog + log() service
├── requirements/     # base / development / production
├── tests/            # pytest suite (85 tests: tenancy, perms, money, stock,
│                     #   entitlements, exports, schedules)
├── docs/             # architecture notes
└── docker-compose.yml
```

## Design notes

- **Service layer**: multi-step operations live in `*/services.py`
  (`SaleService`, `InventoryService`, `PaymentService`, `InvoiceService`,
  `SubscriptionService`, `BusinessService`). Views stay thin.
- **Receipt/invoice numbering**: sequential per business via row-locked
  counter on `Business.settings` — race-safe, gap-tolerant.
- **Usage metering**: `UsageRecord` per business/metric/month powers
  `check_limit`/`enforce_limit` and `can_use_feature` — plan limits are data
  on `Plan.limits`/`Plan.features`, never `if plan == "PRO"` in views.
- **Messaging providers**: `notifications/providers/` — `console` provider
  ships by default; adding Selcom/M-Pesa/WhatsApp Cloud means subclassing
  `SMSProvider`/`WhatsAppProvider` and registering it — no core changes.
- **Celery Beat**: `seed_cron` registers overdue-invoice, low-stock,
  subscription-expiry and usage-aggregation tasks (all idempotent).
