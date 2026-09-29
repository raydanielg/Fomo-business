"""Report selectors — normalized, scope-aware, DB-aggregated.

Every handler returns:
{
    "columns": [{"key": ..., "label": ..., "type": "text|money|number|date"}],
    "rows":    [ {column_key: value, ...}, ... ],
    "summary": {...},
    "period":  {"start": ..., "end": ...},
}

`scope` enforces data visibility:
    {"user_only": bool, "branch_ids": set|None, "user_id": str|None}
branch_ids=None means all business branches the member may access.
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import (
    Avg, Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value,
)
from django.db.models.functions import Coalesce, TruncDate, TruncWeek, TruncMonth
from django.utils import timezone

from apps.customers.models import Customer
from apps.expenses.models import Expense
from apps.inventory.models import InventoryMovement, StockLevel
from apps.invoices.models import Invoice
from apps.payments.models import Payment
from apps.products.models import Product
from apps.sales.models import Sale, SaleItem
from apps.suppliers.models import Supplier
from apps.memberships.models import Membership

MONEY = DecimalField(max_digits=20, decimal_places=2)
ZERO_D = Value(Decimal("0"), output_field=MONEY)


# ---------------------------------------------------------------------------
# scope helpers
# ---------------------------------------------------------------------------

def _dates(params):
    today = timezone.now().date()
    start = params.get("start_date") or today - timedelta(days=30)
    end = params.get("end_date") or today
    return start, end


def _scope_sales(qs, scope, params):
    """Apply tenant+scope+filters to a Sale queryset."""
    if scope["branch_ids"] is not None:
        qs = qs.filter(branch_id__in=scope["branch_ids"])
    if scope.get("user_only") and scope.get("user_id"):
        qs = qs.filter(cashier_id=scope["user_id"])
    if params.get("branch"):
        qs = qs.filter(branch_id=params["branch"])
    if params.get("staff"):
        qs = qs.filter(cashier_id=params["staff"])
    if params.get("customer"):
        qs = qs.filter(customer_id=params["customer"])
    if params.get("status"):
        qs = qs.filter(status=params["status"])
    return qs


def _scope_items(qs, scope, params):
    """Apply scope to a SaleItem queryset (branch lives on sale)."""
    if scope["branch_ids"] is not None:
        qs = qs.filter(sale__branch_id__in=scope["branch_ids"])
    if scope.get("user_only") and scope.get("user_id"):
        qs = qs.filter(sale__cashier_id=scope["user_id"])
    if params.get("branch"):
        qs = qs.filter(sale__branch_id=params["branch"])
    if params.get("staff"):
        qs = qs.filter(sale__cashier_id=params["staff"])
    if params.get("customer"):
        qs = qs.filter(sale__customer_id=params["customer"])
    if params.get("product"):
        qs = qs.filter(product_id=params["product"])
    if params.get("category"):
        qs = qs.filter(product__category_id=params["category"])
    return qs


def _scope_stock(qs, scope, params):
    if scope["branch_ids"] is not None:
        qs = qs.filter(branch_id__in=scope["branch_ids"])
    if params.get("branch"):
        qs = qs.filter(branch_id=params["branch"])
    if params.get("product"):
        qs = qs.filter(product_id=params["product"])
    return qs


def _scope_expenses(qs, scope, params):
    if scope["branch_ids"] is not None:
        qs = qs.filter(branch_id__in=scope["branch_ids"])
    if scope.get("user_only") and scope.get("user_id"):
        qs = qs.filter(created_by_id=scope["user_id"])
    if params.get("branch"):
        qs = qs.filter(branch_id=params["branch"])
    if params.get("category"):
        qs = qs.filter(category_id=params["category"])
    if params.get("payment_method"):
        qs = qs.filter(payment_method=params["payment_method"])
    return qs


def _scope_payments(qs, scope, params):
    if scope["branch_ids"] is not None:
        qs = qs.filter(branch_id__in=scope["branch_ids"])
    if scope.get("user_only") and scope.get("user_id"):
        qs = qs.filter(received_by_id=scope["user_id"])
    if params.get("branch"):
        qs = qs.filter(branch_id=params["branch"])
    if params.get("payment_method"):
        qs = qs.filter(method=params["payment_method"])
    if params.get("status"):
        qs = qs.filter(status=params["status"])
    return qs


def _col(key, label, type_="text"):
    return {"key": key, "label": label, "type": type_}


def _period(start, end):
    return {"start": str(start), "end": str(end)}


# ---------------------------------------------------------------------------
# report handlers
# ---------------------------------------------------------------------------

def _r_sales_summary(business, scope, params):
    start, end = _dates(params)
    qs = _scope_sales(
        Sale.objects.filter(business=business, status="completed",
                            created_at__date__range=[start, end]),
        scope, params,
    )
    totals = qs.aggregate(
        count=Count("id"),
        subtotal=Coalesce(Sum("subtotal"), ZERO_D),
        discount=Coalesce(Sum("discount"), ZERO_D),
        tax=Coalesce(Sum("tax"), ZERO_D),
        total=Coalesce(Sum("total"), ZERO_D),
        paid=Coalesce(Sum("amount_paid"), ZERO_D),
    )
    rows = list(
        qs.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(sales_count=Count("id"), total=Sum("total"), tax=Sum("tax"),
                  discount=Sum("discount"))
        .order_by("day")
    )
    return {
        "columns": [_col("day", "Date", "date"), _col("sales_count", "Sales", "number"),
                    _col("total", "Total", "money"), _col("tax", "Tax", "money"),
                    _col("discount", "Discount", "money")],
        "rows": rows,
        "summary": {k: str(v) if isinstance(v, Decimal) else v
                    for k, v in totals.items()},
        "period": _period(start, end),
    }


def _r_sales_detailed(business, scope, params):
    start, end = _dates(params)
    qs = _scope_sales(
        Sale.objects.filter(business=business, created_at__date__range=[start, end])
        .select_related("branch", "customer", "cashier"),
        scope, params,
    ).order_by("-created_at")[:5000]
    rows = [
        {
            "receipt": s.receipt_number, "date": str(s.created_at.date()),
            "branch": s.branch.name,
            "customer": s.customer.name if s.customer else "",
            "cashier": s.cashier.email if s.cashier else "",
            "status": s.status, "payment_status": s.payment_status,
            "total": s.total, "paid": s.amount_paid, "balance": s.balance_due,
        }
        for s in qs
    ]
    return {
        "columns": [_col("receipt", "Receipt"), _col("date", "Date", "date"),
                    _col("branch", "Branch"), _col("customer", "Customer"),
                    _col("cashier", "Cashier"), _col("status", "Status"),
                    _col("payment_status", "Payment"),
                    _col("total", "Total", "money"), _col("paid", "Paid", "money"),
                    _col("balance", "Balance", "money")],
        "rows": rows,
        "summary": {"count": len(rows)},
        "period": _period(start, end),
    }


def _r_sales_by_product(business, scope, params):
    start, end = _dates(params)
    qs = _scope_items(
        SaleItem.objects.filter(sale__business=business, sale__status="completed",
                                sale__created_at__date__range=[start, end]),
        scope, params,
    )
    rows = list(
        qs.values("product__name", "product__sku")
        .annotate(quantity=Sum("quantity"), revenue=Sum("total"),
                  margin=Sum(ExpressionWrapper(
                      (F("unit_price") - F("product__cost_price")) * F("quantity"),
                      output_field=MONEY)))
        .order_by("-revenue")[:500]
    )
    for r in rows:
        r["product"] = r.pop("product__name")
        r["sku"] = r.pop("product__sku")
    return {
        "columns": [_col("product", "Product"), _col("sku", "SKU"),
                    _col("quantity", "Qty", "number"),
                    _col("revenue", "Revenue", "money"),
                    _col("margin", "Margin", "money")],
        "rows": rows,
        "summary": {},
        "period": _period(start, end),
    }


def _r_sales_by_customer(business, scope, params):
    start, end = _dates(params)
    qs = _scope_sales(
        Sale.objects.filter(business=business, status="completed",
                            created_at__date__range=[start, end],
                            customer__isnull=False),
        scope, params,
    )
    rows = list(
        qs.values("customer__name", "customer__phone")
        .annotate(sales_count=Count("id"), total=Sum("total"))
        .order_by("-total")[:500]
    )
    for r in rows:
        r["customer"] = r.pop("customer__name")
        r["phone"] = r.pop("customer__phone")
    return {
        "columns": [_col("customer", "Customer"), _col("phone", "Phone"),
                    _col("sales_count", "Sales", "number"),
                    _col("total", "Total", "money")],
        "rows": rows, "summary": {}, "period": _period(start, end),
    }


def _r_sales_by_staff(business, scope, params):
    start, end = _dates(params)
    qs = _scope_sales(
        Sale.objects.filter(business=business, status="completed",
                            created_at__date__range=[start, end],
                            cashier__isnull=False),
        scope, params,
    )
    # staff dimension: never narrow by user_only — the report shows the team
    qs = qs.exclude(cashier_id=scope["user_id"]) if scope.get("user_only") else qs
    rows = list(
        qs.values("cashier__email", "cashier__first_name", "cashier__last_name")
        .annotate(sales_count=Count("id"), total=Sum("total"))
        .order_by("-total")
    )
    for r in rows:
        r["staff"] = (r.pop("cashier__first_name") + " "
                      + r.pop("cashier__last_name")).strip() or r.pop("cashier__email")
        r.pop("cashier__email", None)
        r.pop("cashier__first_name", None)
        r.pop("cashier__last_name", None)
    return {
        "columns": [_col("staff", "Staff"), _col("sales_count", "Sales", "number"),
                    _col("total", "Total", "money")],
        "rows": rows, "summary": {}, "period": _period(start, end),
    }


def _r_inventory_summary(business, scope, params):
    qs = _scope_stock(
        StockLevel.objects.filter(business=business)
        .select_related("product", "branch"), scope, params,
    )
    agg = qs.aggregate(
        products=Count("product", distinct=True),
        units=Coalesce(Sum("quantity"), Value(Decimal("0"))),
        value=Coalesce(
            Sum(ExpressionWrapper(F("quantity") * F("product__cost_price"),
                                  output_field=MONEY)), ZERO_D),
    )
    return {
        "columns": [_col("metric", "Metric"), _col("value", "Value")],
        "rows": [
            {"metric": "Products in stock", "value": agg["products"]},
            {"metric": "Total units", "value": str(agg["units"])},
            {"metric": "Stock value", "value": str(agg["value"])},
        ],
        "summary": agg,
        "period": None,
    }


def _r_inventory_valuation(business, scope, params):
    qs = _scope_stock(
        StockLevel.objects.filter(business=business)
        .select_related("product", "branch"), scope, params,
    ).annotate(value=ExpressionWrapper(
        F("quantity") * F("product__cost_price"), output_field=MONEY))
    rows = [
        {"product": s.product.name, "sku": s.product.sku,
         "branch": s.branch.name, "quantity": s.quantity,
         "unit_cost": s.product.cost_price, "value": s.value}
        for s in qs.order_by("product__name")[:2000]
    ]
    total = sum(r["value"] for r in rows)
    return {
        "columns": [_col("product", "Product"), _col("sku", "SKU"),
                    _col("branch", "Branch"), _col("quantity", "Qty", "number"),
                    _col("unit_cost", "Unit Cost", "money"),
                    _col("value", "Value", "money")],
        "rows": rows,
        "summary": {"total_value": str(total)},
        "period": None,
    }


def _r_inventory_movement(business, scope, params):
    start, end = _dates(params)
    qs = InventoryMovement.objects.filter(
        business=business, created_at__date__range=[start, end],
    ).select_related("product", "branch", "created_by")
    if scope["branch_ids"] is not None:
        qs = qs.filter(branch_id__in=scope["branch_ids"])
    if params.get("branch"):
        qs = qs.filter(branch_id=params["branch"])
    if params.get("product"):
        qs = qs.filter(product_id=params["product"])
    if params.get("movement_type"):
        qs = qs.filter(movement_type=params["movement_type"])
    rows = [
        {"date": str(m.created_at.date()), "product": m.product.name,
         "branch": m.branch.name, "type": m.movement_type,
         "quantity": m.quantity, "unit_cost": m.unit_cost,
         "balance_after": m.balance_after,
         "by": m.created_by.email if m.created_by else "",
         "reference": m.reference_id}
        for m in qs.order_by("-created_at")[:5000]
    ]
    return {
        "columns": [_col("date", "Date", "date"), _col("product", "Product"),
                    _col("branch", "Branch"), _col("type", "Type"),
                    _col("quantity", "Qty", "number"),
                    _col("unit_cost", "Unit Cost", "money"),
                    _col("balance_after", "Balance", "number"),
                    _col("by", "By"), _col("reference", "Ref")],
        "rows": rows, "summary": {"count": len(rows)},
        "period": _period(start, end),
    }


def _r_inventory_low_stock(business, scope, params):
    qs = _scope_stock(
        StockLevel.objects.filter(
            business=business, product__track_inventory=True,
            product__is_active=True, product__low_stock_threshold__gt=0,
            quantity__lte=F("product__low_stock_threshold"),
        ).select_related("product", "branch"), scope, params,
    )
    rows = [
        {"product": s.product.name, "sku": s.product.sku,
         "branch": s.branch.name, "quantity": s.quantity,
         "threshold": s.product.low_stock_threshold}
        for s in qs.order_by("quantity")[:1000]
    ]
    return {
        "columns": [_col("product", "Product"), _col("sku", "SKU"),
                    _col("branch", "Branch"), _col("quantity", "Qty", "number"),
                    _col("threshold", "Threshold", "number")],
        "rows": rows, "summary": {"count": len(rows)}, "period": None,
    }


def _r_expenses_summary(business, scope, params):
    start, end = _dates(params)
    qs = _scope_expenses(
        Expense.objects.filter(business=business,
                               expense_date__range=[start, end]), scope, params)
    totals = qs.aggregate(count=Count("id"),
                          total=Coalesce(Sum("amount"), ZERO_D))
    rows = list(
        qs.values("expense_date")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("expense_date")
    )
    for r in rows:
        r["date"] = str(r.pop("expense_date"))
    return {
        "columns": [_col("date", "Date", "date"), _col("count", "Count", "number"),
                    _col("total", "Total", "money")],
        "rows": rows, "summary": totals, "period": _period(start, end),
    }


def _r_expenses_by_category(business, scope, params):
    start, end = _dates(params)
    qs = _scope_expenses(
        Expense.objects.filter(business=business,
                               expense_date__range=[start, end]), scope, params)
    rows = list(
        qs.values("category__name")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )
    for r in rows:
        r["category"] = r.pop("category__name")
    return {
        "columns": [_col("category", "Category"), _col("count", "Count", "number"),
                    _col("total", "Total", "money")],
        "rows": rows, "summary": {}, "period": _period(start, end),
    }


def _r_customers_summary(business, scope, params):
    start, end = _dates(params)
    qs = Customer.objects.filter(business=business).annotate(
        sales_count=Count("sales", filter=Q(
            sales__status="completed",
            sales__created_at__date__range=[start, end])),
        sales_total=Coalesce(Sum("sales__total", filter=Q(
            sales__status="completed",
            sales__created_at__date__range=[start, end])), ZERO_D),
    ).order_by("-sales_total")
    if scope.get("user_only") and scope.get("user_id"):
        qs = qs.filter(sales__cashier_id=scope["user_id"])
    rows = [
        {"customer": c.name, "phone": c.phone, "email": c.email,
         "balance": c.current_balance, "sales_count": c.sales_count,
         "sales_total": c.sales_total}
        for c in qs[:1000]
    ]
    return {
        "columns": [_col("customer", "Customer"), _col("phone", "Phone"),
                    _col("email", "Email"), _col("balance", "Balance", "money"),
                    _col("sales_count", "Sales", "number"),
                    _col("sales_total", "Total", "money")],
        "rows": rows, "summary": {}, "period": _period(start, end),
    }


def _r_customers_purchase_history(business, scope, params):
    start, end = _dates(params)
    qs = _scope_sales(
        Sale.objects.filter(business=business, status="completed",
                            created_at__date__range=[start, end],
                            customer__isnull=False)
        .select_related("customer", "branch"), scope, params,
    )
    rows = [
        {"customer": s.customer.name, "receipt": s.receipt_number,
         "date": str(s.created_at.date()), "branch": s.branch.name,
         "total": s.total, "paid": s.amount_paid, "balance": s.balance_due}
        for s in qs.order_by("-created_at")[:2000]
    ]
    return {
        "columns": [_col("customer", "Customer"), _col("receipt", "Receipt"),
                    _col("date", "Date", "date"), _col("branch", "Branch"),
                    _col("total", "Total", "money"), _col("paid", "Paid", "money"),
                    _col("balance", "Balance", "money")],
        "rows": rows, "summary": {"count": len(rows)}, "period": _period(start, end),
    }


def _r_customers_outstanding(business, scope, params):
    qs = Customer.objects.filter(
        business=business, is_active=True, current_balance__gt=0,
    )
    if scope.get("user_only") and scope.get("user_id"):
        qs = qs.filter(sales__cashier_id=scope["user_id"]).distinct()
    rows = [
        {"customer": c.name, "phone": c.phone,
         "balance": c.current_balance, "credit_limit": c.credit_limit}
        for c in qs.order_by("-current_balance")[:1000]
    ]
    return {
        "columns": [_col("customer", "Customer"), _col("phone", "Phone"),
                    _col("balance", "Balance", "money"),
                    _col("credit_limit", "Credit Limit", "money")],
        "rows": rows,
        "summary": {
            "total_outstanding": str(sum(r["balance"] for r in rows)),
        },
        "period": None,
    }


def _profit_items(business, scope, params, start, end):
    return _scope_items(
        SaleItem.objects.filter(sale__business=business,
                                sale__status="completed",
                                sale__created_at__date__range=[start, end]),
        scope, params,
    )


def _r_profit_summary(business, scope, params):
    start, end = _dates(params)
    items = _profit_items(business, scope, params, start, end)
    revenue = items.aggregate(
        revenue=Coalesce(Sum(F("quantity") * F("unit_price") - F("discount"),
                             output_field=MONEY), ZERO_D),
        tax=Coalesce(Sum("tax"), ZERO_D),
        cogs=Coalesce(Sum(F("quantity") * F("product__cost_price"),
                          output_field=MONEY), ZERO_D),
    )
    exp_qs = _scope_expenses(
        Expense.objects.filter(business=business,
                               expense_date__range=[start, end]), scope, params)
    expenses = exp_qs.aggregate(t=Coalesce(Sum("amount"), ZERO_D))["t"]
    gross = revenue["revenue"] - revenue["cogs"]
    return {
        "columns": [_col("metric", "Metric"), _col("value", "Value", "money")],
        "rows": [
            {"metric": "Revenue", "value": revenue["revenue"]},
            {"metric": "Cost of goods sold", "value": revenue["cogs"]},
            {"metric": "Gross profit", "value": gross},
            {"metric": "Expenses", "value": expenses},
            {"metric": "Net profit", "value": gross - expenses},
            {"metric": "Tax collected", "value": revenue["tax"]},
        ],
        "summary": {"revenue": str(revenue["revenue"]),
                    "cogs": str(revenue["cogs"]),
                    "gross_profit": str(gross), "expenses": str(expenses),
                    "net_profit": str(gross - expenses)},
        "period": _period(start, end),
    }


def _r_profit_by_product(business, scope, params):
    start, end = _dates(params)
    items = _profit_items(business, scope, params, start, end)
    rows = list(
        items.values("product__name", "product__sku")
        .annotate(
            quantity=Sum("quantity"),
            revenue=Sum(F("quantity") * F("unit_price") - F("discount"),
                        output_field=MONEY),
            cost=Sum(F("quantity") * F("product__cost_price"),
                     output_field=MONEY),
        )
        .annotate(margin=ExpressionWrapper(F("revenue") - F("cost"),
                                         output_field=MONEY))
        .order_by("-margin")[:500]
    )
    for r in rows:
        r["product"] = r.pop("product__name")
        r["sku"] = r.pop("product__sku")
    return {
        "columns": [_col("product", "Product"), _col("sku", "SKU"),
                    _col("quantity", "Qty", "number"),
                    _col("revenue", "Revenue", "money"),
                    _col("cost", "Cost", "money"),
                    _col("margin", "Margin", "money")],
        "rows": rows, "summary": {}, "period": _period(start, end),
    }


def _r_profit_by_branch(business, scope, params):
    start, end = _dates(params)
    items = _profit_items(business, scope, params, start, end)
    rows = list(
        items.values("sale__branch__name")
        .annotate(
            revenue=Sum(F("quantity") * F("unit_price") - F("discount"),
                        output_field=MONEY),
            cost=Sum(F("quantity") * F("product__cost_price"),
                     output_field=MONEY),
            sales_count=Count("sale", distinct=True),
        )
        .annotate(margin=ExpressionWrapper(F("revenue") - F("cost"),
                                         output_field=MONEY))
        .order_by("-margin")
    )
    for r in rows:
        r["branch"] = r.pop("sale__branch__name")
    return {
        "columns": [_col("branch", "Branch"),
                    _col("sales_count", "Sales", "number"),
                    _col("revenue", "Revenue", "money"),
                    _col("cost", "Cost", "money"),
                    _col("margin", "Margin", "money")],
        "rows": rows, "summary": {}, "period": _period(start, end),
    }


def _r_payments_summary(business, scope, params):
    start, end = _dates(params)
    qs = _scope_payments(
        Payment.objects.filter(business=business,
                               paid_at__date__range=[start, end]), scope, params)
    totals = qs.aggregate(
        count=Count("id"),
        received=Coalesce(Sum("amount", filter=Q(status="completed")), ZERO_D),
        refunded=Coalesce(Sum("amount", filter=Q(status="refunded")), ZERO_D),
    )
    rows = list(
        qs.annotate(day=TruncDate("paid_at"))
        .values("day")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("day")
    )
    for r in rows:
        r["date"] = str(r.pop("day"))
    return {
        "columns": [_col("date", "Date", "date"), _col("count", "Count", "number"),
                    _col("total", "Total", "money")],
        "rows": rows, "summary": totals, "period": _period(start, end),
    }


def _r_payments_by_method(business, scope, params):
    start, end = _dates(params)
    qs = _scope_payments(
        Payment.objects.filter(business=business,
                               paid_at__date__range=[start, end]), scope, params)
    rows = list(
        qs.values("method", "status")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("method")
    )
    return {
        "columns": [_col("method", "Method"), _col("status", "Status"),
                    _col("count", "Count", "number"),
                    _col("total", "Total", "money")],
        "rows": rows, "summary": {}, "period": _period(start, end),
    }


def _r_staff_performance(business, scope, params):
    start, end = _dates(params)
    qs = Sale.objects.filter(
        business=business, status="completed",
        created_at__date__range=[start, end], cashier__isnull=False,
    )
    if scope["branch_ids"] is not None:
        qs = qs.filter(branch_id__in=scope["branch_ids"])
    if params.get("branch"):
        qs = qs.filter(branch_id=params["branch"])
    if params.get("staff"):
        qs = qs.filter(cashier_id=params["staff"])
    rows = list(
        qs.values("cashier__email", "cashier__first_name", "cashier__last_name")
        .annotate(sales_count=Count("id"), total_amount=Sum("total"),
                  avg_sale=Avg("total"))
        .order_by("-total_amount")
    )
    for r in rows:
        name = (r.pop("cashier__first_name") + " "
                + r.pop("cashier__last_name")).strip()
        email = r.pop("cashier__email")
        r["staff"] = name or email
        r["total"] = r.pop("total_amount")
    return {
        "columns": [_col("staff", "Staff"),
                    _col("sales_count", "Sales", "number"),
                    _col("total", "Total", "money"),
                    _col("avg_sale", "Avg Sale", "money")],
        "rows": rows, "summary": {}, "period": _period(start, end),
    }


def _r_branches_performance(business, scope, params):
    start, end = _dates(params)
    qs = Sale.objects.filter(
        business=business, status="completed",
        created_at__date__range=[start, end],
    )
    if scope["branch_ids"] is not None:
        qs = qs.filter(branch_id__in=scope["branch_ids"])
    rows = list(
        qs.values("branch__name")
        .annotate(sales_count=Count("id"), total=Sum("total"),
                  paid=Sum("amount_paid"))
        .order_by("-total")
    )
    for r in rows:
        r["branch"] = r.pop("branch__name")
    return {
        "columns": [_col("branch", "Branch"),
                    _col("sales_count", "Sales", "number"),
                    _col("total", "Total", "money"),
                    _col("paid", "Paid", "money")],
        "rows": rows, "summary": {}, "period": _period(start, end),
    }


def _r_tax_summary(business, scope, params):
    start, end = _dates(params)
    items = _profit_items(business, scope, params, start, end)
    rows = list(
        items.values("product__tax_rate")
        .annotate(
            taxable=Sum(F("quantity") * F("unit_price") - F("discount"),
                        output_field=MONEY),
            tax=Sum("tax"),
        )
        .order_by("product__tax_rate")
    )
    for r in rows:
        r["rate"] = r.pop("product__tax_rate")
    total = items.aggregate(t=Coalesce(Sum("tax"), ZERO_D))["t"]
    return {
        "columns": [_col("rate", "Tax Rate %", "number"),
                    _col("taxable", "Taxable", "money"),
                    _col("tax", "Tax", "money")],
        "rows": rows, "summary": {"total_tax": str(total)},
        "period": _period(start, end),
    }


def _trend(items, start, end, params, value_expr):
    group_by = params.get("group_by", "day")
    trunc = {"day": TruncDate, "week": TruncWeek, "month": TruncMonth}.get(
        group_by, TruncDate
    )
    rows = list(
        items.annotate(bucket=trunc("sale__created_at"))
        .values("bucket")
        .annotate(value=value_expr, count=Count("id"))
        .order_by("bucket")
    )
    for r in rows:
        r["period"] = str(r.pop("bucket"))
    return rows


def _r_sales_trends(business, scope, params):
    start, end = _dates(params)
    items = _profit_items(business, scope, params, start, end)
    rows = _trend(items, start, end, params, Sum("total"))
    return {
        "columns": [_col("period", "Period"), _col("value", "Revenue", "money"),
                    _col("count", "Line Items", "number")],
        "rows": rows, "summary": {}, "period": _period(start, end),
    }


def _r_profit_trends(business, scope, params):
    start, end = _dates(params)
    items = _profit_items(business, scope, params, start, end)
    rows = _trend(
        items, start, end, params,
        Sum(ExpressionWrapper(
            (F("unit_price") - F("product__cost_price")) * F("quantity")
            - F("discount"), output_field=MONEY)),
    )
    return {
        "columns": [_col("period", "Period"), _col("value", "Profit", "money"),
                    _col("count", "Line Items", "number")],
        "rows": rows, "summary": {}, "period": _period(start, end),
    }


def _r_business_comparison(business, scope, params):
    # compares this period vs prior equivalent period
    start, end = _dates(params)
    span = (end - start).days or 1
    prior_end = start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=span)

    def totals(s, e):
        qs = _scope_sales(
            Sale.objects.filter(business=business, status="completed",
                                created_at__date__range=[s, e]),
            scope, params)
        return qs.aggregate(total=Coalesce(Sum("total"), ZERO_D),
                            count=Count("id"))

    cur, prev = totals(start, end), totals(prior_start, prior_end)
    exp_qs = _scope_expenses(Expense.objects.filter(business=business), scope, params)
    cur_exp = exp_qs.filter(expense_date__range=[start, end]).aggregate(
        t=Coalesce(Sum("amount"), ZERO_D))["t"]
    prev_exp = exp_qs.filter(expense_date__range=[prior_start, prior_end]).aggregate(
        t=Coalesce(Sum("amount"), ZERO_D))["t"]

    rows = [
        {"metric": "Revenue", "current": cur["total"], "previous": prev["total"]},
        {"metric": "Sales count", "current": cur["count"], "previous": prev["count"]},
        {"metric": "Expenses", "current": cur_exp, "previous": prev_exp},
    ]
    return {
        "columns": [_col("metric", "Metric"), _col("current", "Current", "money"),
                    _col("previous", "Previous", "money")],
        "rows": rows,
        "summary": {},
        "period": {"start": str(start), "end": str(end),
                   "previous_start": str(prior_start),
                   "previous_end": str(prior_end)},
    }


def _r_supplier_summary(business, scope, params):
    start, end = _dates(params)
    qs = Supplier.objects.filter(business=business).annotate(
        purchases_count=Count("purchases", filter=Q(
            purchases__status="received",
            purchases__created_at__date__range=[start, end])),
        purchases_total=Coalesce(Sum("purchases__total", filter=Q(
            purchases__status="received",
            purchases__created_at__date__range=[start, end])), ZERO_D),
    ).order_by("-purchases_total")
    rows = [
        {"supplier": s.name, "phone": s.phone, "balance": s.balance,
         "purchases_count": s.purchases_count,
         "purchases_total": s.purchases_total}
        for s in qs[:1000]
    ]
    return {
        "columns": [_col("supplier", "Supplier"), _col("phone", "Phone"),
                    _col("balance", "Balance", "money"),
                    _col("purchases_count", "Purchases", "number"),
                    _col("purchases_total", "Total", "money")],
        "rows": rows, "summary": {}, "period": _period(start, end),
    }


# ---------------------------------------------------------------------------
# dashboard (not a catalog report — kept for the web/mobile home screen)
# ---------------------------------------------------------------------------

def dashboard(business, request):
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    month_start = today.replace(day=1)

    sales_today = Sale.objects.filter(
        business=business, status=Sale.Status.COMPLETED, created_at__date=today
    ).aggregate(
        total=Coalesce(Sum("total"), ZERO_D),
        count=Count("id"),
    )

    sales_yesterday = Sale.objects.filter(
        business=business, status=Sale.Status.COMPLETED,
        created_at__date=yesterday,
    ).aggregate(total=Coalesce(Sum("total"), ZERO_D))["total"]

    if sales_yesterday > 0:
        sales_change_pct = (
            (sales_today["total"] - sales_yesterday) / sales_yesterday
        ) * 100
    else:
        sales_change_pct = None

    expenses_today = Expense.objects.filter(
        business=business, expense_date=today
    ).aggregate(total=Coalesce(Sum("amount"), ZERO_D))["total"]

    profit_today = (
        SaleItem.objects.filter(
            sale__business=business, sale__status=Sale.Status.COMPLETED,
            sale__created_at__date=today,
        )
        .annotate(margin=ExpressionWrapper(
            (F("unit_price") - F("product__cost_price")) * F("quantity")
            - F("discount"), output_field=MONEY))
        .aggregate(total=Coalesce(Sum("margin"), ZERO_D))["total"]
    )

    low_stock_qs = (
        StockLevel.objects.filter(
            business=business, product__track_inventory=True,
            product__is_active=True, product__low_stock_threshold__gt=0,
            quantity__lte=F("product__low_stock_threshold"),
        ).select_related("product", "branch")
    )

    unpaid_invoices = Invoice.objects.filter(
        business=business,
        status__in=[Invoice.Status.ISSUED, Invoice.Status.PARTIALLY_PAID,
                    Invoice.Status.OVERDUE],
    ).aggregate(count=Count("id"), balance=Coalesce(Sum("balance_due"), ZERO_D))

    overdue_invoices = Invoice.objects.filter(
        business=business, status=Invoice.Status.OVERDUE,
    ).count()

    # daily sales buckets for the chart — ?days=7|30|90, capped
    try:
        trend_days = int(request.GET.get("days", "7"))
    except (TypeError, ValueError):
        trend_days = 7
    trend_days = max(1, min(trend_days, 90))
    trend_start = today - timedelta(days=trend_days - 1)

    trend_qs = (
        Sale.objects.filter(
            business=business, status=Sale.Status.COMPLETED,
            created_at__date__gte=trend_start,
        )
        .annotate(d=TruncDate("created_at"))
        .values("d")
        .annotate(total=Sum("total"))
    )
    by_day = {row["d"]: row["total"] for row in trend_qs}
    expense_qs = (
        Expense.objects.filter(
            business=business, expense_date__gte=trend_start,
        )
        .values("expense_date")
        .annotate(total=Sum("amount"))
    )
    exp_by_day = {row["expense_date"]: row["total"] for row in expense_qs}
    trend = [
        {"date": (trend_start + timedelta(days=i)).isoformat(),
         "total": str(by_day.get(trend_start + timedelta(days=i), ZERO_D)),
         "expenses": str(exp_by_day.get(trend_start + timedelta(days=i), ZERO_D))}
        for i in range(trend_days)
    ]

    recent_sales = (
        Sale.objects.filter(business=business, status=Sale.Status.COMPLETED)
        .select_related("branch", "customer", "cashier")
        .order_by("-created_at")[:10]
    )

    return {
        "today": {"sales": sales_today["total"],
                  "expenses": expenses_today,
                  "estimated_profit": profit_today,
                  "transaction_count": sales_today["count"]},
        "yesterday": {"sales": sales_yesterday},
        "sales_change_pct": (
            str(sales_change_pct.quantize(Decimal("0.1")))
            if sales_change_pct is not None else None
        ),
        "trend": trend,
        "trend_days": trend_days,
        "totals": {
            "customers": Customer.objects.filter(
                business=business, is_active=True).count(),
            "new_customers_month": Customer.objects.filter(
                business=business, is_active=True,
                created_at__date__gte=month_start).count(),
            "products": Product.objects.filter(
                business=business, is_active=True).count(),
            "out_of_stock": StockLevel.objects.filter(
                business=business, product__track_inventory=True,
                product__is_active=True, quantity__lte=0).count(),
            "staff": Membership.objects.filter(
                business=business, status="active").count(),
        },
        "overdue_invoices": overdue_invoices,
        "low_stock": [
            {"product_id": str(s.product_id), "product": s.product.name,
             "branch": s.branch.name, "quantity": str(s.quantity),
             "threshold": str(s.product.low_stock_threshold)}
            for s in low_stock_qs[:20]
        ],
        "unpaid_invoices": unpaid_invoices,
        "recent_sales": [
            {"id": str(s.id), "receipt_number": s.receipt_number,
             "total": str(s.total), "status": s.status,
             "customer": s.customer.name if s.customer else None,
             "cashier": s.cashier.email if s.cashier else None,
             "created_at": s.created_at.isoformat()}
            for s in recent_sales
        ],
    }


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------

REPORT_HANDLERS = {
    "sales.summary": _r_sales_summary,
    "sales.detailed": _r_sales_detailed,
    "sales.by_product": _r_sales_by_product,
    "sales.by_customer": _r_sales_by_customer,
    "sales.by_staff": _r_sales_by_staff,
    "inventory.summary": _r_inventory_summary,
    "inventory.valuation": _r_inventory_valuation,
    "inventory.movement": _r_inventory_movement,
    "inventory.low_stock": _r_inventory_low_stock,
    "expenses.summary": _r_expenses_summary,
    "expenses.by_category": _r_expenses_by_category,
    "customers.summary": _r_customers_summary,
    "customers.purchase_history": _r_customers_purchase_history,
    "customers.outstanding_balances": _r_customers_outstanding,
    "profit.summary": _r_profit_summary,
    "profit.by_product": _r_profit_by_product,
    "profit.by_branch": _r_profit_by_branch,
    "payments.summary": _r_payments_summary,
    "payments.by_method": _r_payments_by_method,
    "staff.performance": _r_staff_performance,
    "branches.performance": _r_branches_performance,
    "tax.summary": _r_tax_summary,
    "suppliers.summary": _r_supplier_summary,
    "advanced.sales_trends": _r_sales_trends,
    "advanced.profit_trends": _r_profit_trends,
    "advanced.business_comparison": _r_business_comparison,
}


def render_report(report_key, business, scope, params):
    handler = REPORT_HANDLERS.get(report_key)
    if handler is None:
        return None
    return handler(business, scope, params)
