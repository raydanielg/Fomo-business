# Fomo API — Frontend Contract

Base URL: `/api/v1/`. Full reference: `GET /api/docs/` (Swagger UI) or
`GET /api/schema/` (OpenAPI 3).

## Auth flow

```
POST /api/v1/auth/register/   → {email, password, password_confirm, first_name?, last_name?, phone?}
POST /api/v1/auth/login/      → {email, password, device_name?} → {access, refresh, user}
POST /api/v1/auth/refresh/    → {refresh} → {access, refresh}  (rotating)
POST /api/v1/auth/logout/     → {refresh}
GET|PATCH /api/v1/auth/me/    → profile
POST /api/v1/auth/change-password/
POST /api/v1/auth/password-reset/          → sends email
POST /api/v1/auth/password-reset/confirm/  → {token, new_password, new_password_confirm}
POST /api/v1/auth/verify-email/            → {token}
POST /api/v1/auth/resend-verification/
GET  /api/v1/auth/sessions/                → device sessions
DELETE /api/v1/auth/sessions/{id}/         → revoke a device
```

Then every business request:

```
Authorization: Bearer <access>
X-Business-ID: <uuid>
```

`GET /api/v1/businesses/` lists the user's businesses — use it to populate a
business switcher; `POST /api/v1/businesses/` provisions a new tenant.

## Conventions

- Lists: `?page=&page_size=&search=&ordering=-created_at` + filter params.
- Errors: `{"success": false, "error": {"code", "message", "details"}, "request_id"}`
- Money fields are decimal strings (`"150.00"`), never floats.
- IDs are UUIDs.
- `X-Request-ID` response header correlates client/server logs.

## Key flows

**POS sale** — `POST /api/v1/sales/`:

```json
{
  "branch_id": "<uuid>",
  "customer_id": "<uuid|null>",
  "items": [{"product_id": "<uuid>", "quantity": "2", "unit_price": "150", "discount": "0"}],
  "discount": "0",
  "payment": {"method": "CASH", "amount": "300", "reference": ""},
  "draft": false
}
```

Server recomputes every line total + tax; `payment.amount` must not exceed
the computed total. `draft: true` parks the sale; `POST …/complete/`,
`…/cancel/`, `…/refund/`, `GET …/receipt/` (PDF) follow.

**Invoice** — `POST /api/v1/invoices/` (same shape + `due_date`,
`issue_immediately`); lifecycle `issue` → `record-payment` → `paid` |
`cancel`.

**Stock** — `POST /api/v1/inventory/adjust/` `{product_id, branch_id, quantity,
direction: in|out, note}`; `POST /api/v1/inventory/transfer/` `{product_id,
from_branch_id, to_branch_id, quantity}`.

**Staff invite** — `POST /api/v1/memberships/staff/invite/` `{email, role_id,
allowed_branch_ids?}`. Invitee accepts via `POST
/api/v1/memberships/mine/{business_id}/accept/` after setting a password from
the email link.

## Error codes worth handling

`AUTH_*`, `BUSINESS_REQUIRED`, `PERMISSION_DENIED`, `INSUFFICIENT_STOCK`
(details carry `available`/`requested`), `INVALID_PAYMENT_AMOUNT`,
`PLAN_LIMIT_REACHED` (402 → upsell), `FEATURE_NOT_AVAILABLE`,
`FEATURE_NOT_INCLUDED` (402 → upgrade CTA; `details.upgrade_available`),
`INVALID_STATE_TRANSITION`, `RATE_LIMITED` (details.wait_seconds).

## Reports & entitlements

Report access = **plan feature AND role permission AND data scope**.

```
GET /api/v1/reports/                          → catalog with per-report access
GET /api/v1/reports/{key}/                    → render (rows/columns/summary)
GET /api/v1/reports/{key}/capabilities/       → view/filter/export/… booleans
GET /api/v1/reports/{key}/filters/            → plan-entitled filters
POST /api/v1/reports/{key}/export/            → {format: csv|xlsx|pdf}
GET /api/v1/reports/dashboard/                → today/totals/low-stock
GET /api/v1/reports/analytics/                → this business's usage stats
GET|POST /api/v1/scheduled-reports/           → scheduled reports CRUD
PATCH|DELETE /api/v1/scheduled-reports/{id}/
GET /api/v1/subscriptions/plans/comparison/   → full plan×feature matrix (public)
```

Report keys are catalog rows (admin-managed): `sales.summary`,
`sales.detailed`, `sales.by_product`, `sales.by_customer`, `sales.by_staff`,
`inventory.summary`, `inventory.valuation`, `inventory.movement`,
`inventory.low_stock`, `expenses.summary`, `expenses.by_category`,
`customers.summary`, `customers.purchase_history`,
`customers.outstanding_balances`, `suppliers.summary`, `profit.summary`,
`profit.by_product`, `profit.by_branch`, `payments.summary`,
`payments.by_method`, `staff.performance`, `branches.performance`,
`tax.summary`, `advanced.sales_trends`, `advanced.profit_trends`,
`advanced.business_comparison`.

Denied access returns the reason + upgrade metadata:

```json
{"success": false, "error": {"code": "FEATURE_NOT_INCLUDED",
  "message": "This feature is not included in your plan.",
  "details": {"reason": "FEATURE_NOT_INCLUDED", "feature": "reports.profit",
              "report": "profit.summary", "upgrade_available": true}}}
```

`capabilities` tells the frontend which controls to render — the backend
re-checks every one on each request.
