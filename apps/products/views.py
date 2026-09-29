from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.models import AuditLog
from apps.audit.services import log as audit_log
from apps.common.mixins import TenantScopedQuerySetMixin
from apps.common.permissions import HasActiveMembership, HasPermission
from apps.subscriptions.services import enforce_limit

from .models import Category, Product, Unit
from .serializers import CategorySerializer, ProductListSerializer, ProductSerializer, UnitSerializer


class CategoryViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    queryset = Category.objects.none()
    serializer_class = CategorySerializer
    permission_classes = [HasActiveMembership, HasPermission]
    permission_map = {
        "list": "products.view",
        "retrieve": "products.view",
        "create": "products.create",
        "update": "products.update",
        "partial_update": "products.update",
        "destroy": "products.delete",
    }
    search_fields = ["name"]
    filterset_fields = ["is_active"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Category.objects.none()
        return Category.objects.filter(business=self.request.business)


class UnitViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    queryset = Unit.objects.none()
    serializer_class = UnitSerializer
    permission_classes = [HasActiveMembership, HasPermission]
    permission_map = {
        "list": "products.view",
        "retrieve": "products.view",
        "create": "products.create",
        "update": "products.update",
        "partial_update": "products.update",
        "destroy": "products.delete",
    }
    search_fields = ["name", "abbreviation"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Unit.objects.none()
        return Unit.objects.filter(business=self.request.business)


class ProductViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    queryset = Product.objects.none()
    permission_classes = [HasActiveMembership, HasPermission]
    permission_map = {
        "list": "products.view",
        "retrieve": "products.view",
        "create": "products.create",
        "update": "products.update",
        "partial_update": "products.update",
        "destroy": "products.delete",
        "stock": "inventory.view",
        "low_stock": "inventory.view",
        "performance": "reports.sales",
    }
    filterset_fields = ["is_active", "category", "track_inventory"]
    search_fields = ["name", "sku", "barcode", "description"]
    ordering_fields = ["name", "selling_price", "created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Product.objects.none()
        qs = (
            Product.objects.filter(business=self.request.business)
            .select_related("category", "unit")
        )
        if self.action == "list":
            from apps.inventory.models import StockLevel
            from django.db.models import DecimalField, Value
            from django.db.models.functions import Coalesce
            from django.db.models import Subquery, OuterRef

            branch_id = self.request.query_params.get("branch")
            stock = StockLevel.objects.filter(product_id=OuterRef("pk"))
            if branch_id:
                stock = stock.filter(branch_id=branch_id)
            qs = qs.annotate(
                total_stock=Coalesce(
                    Subquery(
                        stock.values("product_id")
                        .annotate(t=Sum("quantity"))
                        .values("t"),
                        output_field=DecimalField(max_digits=14,
                                                  decimal_places=2),
                    ),
                    Value(0, output_field=DecimalField(max_digits=14,
                                                       decimal_places=2)),
                )
            )
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        return ProductSerializer

    def perform_create(self, serializer):
        count = Product.objects.filter(business=self.request.business).count()
        enforce_limit(self.request.business, "max_products", current_value=count)
        product = serializer.save(
            business=self.request.business, created_by=self.request.user
        )
        audit_log(
            AuditLog.Action.PRODUCT_CREATED,
            business=self.request.business, user=self.request.user,
            resource_type="Product", resource_id=product.id,
            new_values={"name": product.name, "sku": product.sku},
        )

    def perform_update(self, serializer):
        old = ProductSerializer(self.get_object()).data
        product = serializer.save()
        audit_log(
            AuditLog.Action.PRODUCT_UPDATED,
            business=self.request.business, user=self.request.user,
            resource_type="Product", resource_id=product.id,
            old_values=old, new_values=ProductSerializer(product).data,
        )

    def perform_destroy(self, instance):
        audit_log(
            AuditLog.Action.PRODUCT_DELETED,
            business=self.request.business, user=self.request.user,
            resource_type="Product", resource_id=instance.id,
            old_values={"name": instance.name, "sku": instance.sku},
        )
        instance.delete()

    @action(detail=True, methods=["get"], url_path="stock")
    def stock(self, request, pk=None):
        product = self.get_object()
        from apps.inventory.models import StockLevel

        levels = (
            StockLevel.objects.filter(product=product)
            .select_related("branch")
            .values("branch_id", "branch__name")
            .annotate(quantity=Sum("quantity"))
        )
        return Response({"success": True, "data": list(levels)})

    @action(detail=True, methods=["get"], url_path="performance")
    def performance(self, request, pk=None):
        """Daily revenue/quantity trend for one product, plus this-month
        vs. last-month revenue change — powers the product detail chart.
        Only counts completed sales; server-computed, never client math.
        """
        from apps.sales.models import SaleItem

        product = self.get_object()
        days = min(int(request.query_params.get("days", 30)), 90)
        start = timezone.now().date() - timedelta(days=days - 1)

        items = SaleItem.objects.filter(
            product=product,
            sale__business=request.business,
            sale__status="completed",
            sale__created_at__date__gte=start,
        )
        daily = (
            items.annotate(day=TruncDate("sale__created_at"))
            .values("day")
            .annotate(quantity=Sum("quantity"), revenue=Sum("total"))
            .order_by("day")
        )
        by_day = {row["day"]: row for row in daily}
        trend = []
        for i in range(days):
            day = start + timedelta(days=i)
            row = by_day.get(day)
            trend.append({
                "date": day.isoformat(),
                "quantity": str(row["quantity"]) if row else "0",
                "revenue": str(row["revenue"]) if row else "0",
            })

        today = timezone.now().date()
        this_month_start = today.replace(day=1)
        last_month_end = this_month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)

        def _revenue_between(start_date, end_date):
            total = SaleItem.objects.filter(
                product=product,
                sale__business=request.business,
                sale__status="completed",
                sale__created_at__date__gte=start_date,
                sale__created_at__date__lte=end_date,
            ).aggregate(t=Sum("total"))["t"]
            return total or Decimal("0")

        this_month = _revenue_between(this_month_start, today)
        last_month = _revenue_between(last_month_start, last_month_end)
        change_pct = (
            float((this_month - last_month) / last_month * 100)
            if last_month > 0
            else (100.0 if this_month > 0 else 0.0)
        )

        return Response({
            "success": True,
            "data": {
                "trend": trend,
                "this_month_revenue": str(this_month),
                "last_month_revenue": str(last_month),
                "change_pct": round(change_pct, 1),
            },
        })

    @action(detail=False, methods=["get"], url_path="low-stock")
    def low_stock(self, request):
        from apps.inventory.services import low_stock_products

        qs = low_stock_products(business_id=request.business.id)
        data = [
            {
                "product_id": str(s.product_id),
                "product": s.product.name,
                "branch_id": str(s.branch_id),
                "branch": s.branch.name,
                "quantity": str(s.quantity),
                "threshold": str(s.product.low_stock_threshold),
            }
            for s in qs
        ]
        return Response({"success": True, "data": data})
