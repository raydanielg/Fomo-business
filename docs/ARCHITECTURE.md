# Fomo Backend — Architecture Notes

## Tenancy model

`X-Business-ID` header → `CurrentBusinessMiddleware` verifies an **active**
`Membership` for the authenticated user and attaches `request.business` +
`request.membership`. If the user isn't a member, the context stays empty and
`HasActiveMembership` returns `BUSINESS_REQUIRED` (400).

All tenant viewsets filter by `request.business` — a `business_id` in the body
is never used for scoping.

## Permissions

`Role.permissions` is a JSON list of strings (`"products.create"`). The seeded
`OWNER` role holds `["*"]`. `HasPermission` reads `permission_map` (per-action)
or `required_permission` on the view. A list of permissions means **any-of**.

Branch scoping: `Membership.allowed_branches` — empty means all branches;
otherwise the member is restricted (enforced in querysets and branch
resolution helpers).

## Money & stock invariants

- All monetary fields are `DecimalField`; totals are computed server-side in
  `SaleService._price_items` / `InvoiceService` from catalog prices.
- `InventoryMovement` is append-only. `StockLevel` is a derived cache updated
  in the same `transaction.atomic()` block under `select_for_update()`.
- Negative stock is rejected unless `Business.allow_negative_stock`.
- Receipt/invoice numbers are allocated from a row-locked sequence on
  `Business.settings` — no duplicates under concurrency.

## Payments

`PaymentService.record_payment` validates amounts (>0, ≤ outstanding),
updates the linked `Sale`/`Invoice` (`amount_paid`, `balance_due`,
`payment_status`) and the customer balance — all in one transaction.

External providers (Selcom, M-Pesa, …) slot in as adapters under
`apps/payments/providers/` (future) — the payment record stays provider-
agnostic (`method`, `reference`, `metadata`).

## Subscriptions & entitlements

`Plan.limits` / `Plan.features` are JSON on the plan row — limits are
configuration, not code. The **Feature**/**PlanFeature** tables are the
canonical entitlement matrix (`PlanFeature.configuration` holds per-plan
limits such as export formats and caps). `subscriptions.services` exposes:

- `can_use_feature(business, "reports.profit")` / `require_feature`
- `check_limit` / `enforce_limit(business, "max_products", current_value=…)`
- `increment_usage(business, metric)` — monthly `UsageRecord` upsert

`reports.entitlements.EntitlementService` composes the full chain for
reports: subscription entitlement ∧ role permission (`reports.<category>`)
∧ data scope (`Role.report_scope` + `Membership.allowed_branches`). All
denials are recorded in `EntitlementEvent`; all views/exports in
`ReportUsage`.

Scheduled reports: `ScheduledReport` rows run via the Celery task
`run_due_scheduled_reports` (every 15 min). On each run the feature is
re-checked — a plan downgrade disables schedules automatically.

## Audit

`audit.services.log(action, business=…, user=…, resource_type=…, …)` —
sanitizes keys containing `password|token|secret|api_key`. Called from every
mutating service. `AuditContextMiddleware` injects IP/UA/request-id.

## Async

Celery tasks live in `apps/notifications/tasks.py` (email/SMS fan-out) plus
scheduled jobs: overdue invoices, low stock, subscription expiry, usage
aggregation — all idempotent. Beat uses the DB scheduler; `seed_cron`
registers them.

## Known trade-offs

- Receipt PDFs are generated synchronously and cached under
  `MEDIA_ROOT/receipts/` — move to a task + object storage when volume grows.
- `Sale`/`Invoice` list endpoints eager-load items; large histories should
  switch to a summary serializer.
- `allowed_branches.exists()` per request is a query — cache on the
  membership or denormalize if it shows up in profiles.
