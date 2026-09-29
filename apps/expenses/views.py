from rest_framework import viewsets

from apps.audit.models import AuditLog
from apps.audit.services import log as audit_log
from apps.common.mixins import TenantScopedQuerySetMixin
from apps.common.permissions import HasActiveMembership, HasPermission

from .models import Expense, ExpenseCategory
from .serializers import ExpenseCategorySerializer, ExpenseSerializer


class ExpenseCategoryViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.none()
    serializer_class = ExpenseCategorySerializer
    permission_classes = [HasActiveMembership, HasPermission]
    permission_map = {
        "list": "expenses.view",
        "retrieve": "expenses.view",
        "create": "expenses.create",
        "update": "expenses.update",
        "partial_update": "expenses.update",
        "destroy": "expenses.delete",
    }
    filterset_fields = ["is_active"]
    search_fields = ["name"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ExpenseCategory.objects.none()
        return ExpenseCategory.objects.filter(business=self.request.business)


class ExpenseViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    queryset = Expense.objects.none()
    serializer_class = ExpenseSerializer
    permission_classes = [HasActiveMembership, HasPermission]
    permission_map = {
        "list": "expenses.view",
        "retrieve": "expenses.view",
        "create": "expenses.create",
        "update": "expenses.update",
        "partial_update": "expenses.update",
        "destroy": "expenses.delete",
    }
    filterset_fields = ["category", "branch", "payment_method", "expense_date"]
    search_fields = ["description", "reference"]
    ordering_fields = ["expense_date", "amount", "created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Expense.objects.none()
        return (
            Expense.objects.filter(business=self.request.business)
            .select_related("category", "branch", "created_by")
        )

    def perform_create(self, serializer):
        expense = serializer.save(
            business=self.request.business, created_by=self.request.user
        )
        audit_log(
            AuditLog.Action.EXPENSE_CREATED,
            business=self.request.business, user=self.request.user,
            resource_type="Expense", resource_id=expense.id,
            new_values={"amount": str(expense.amount)},
        )

    def perform_update(self, serializer):
        expense = serializer.save()
        audit_log(
            AuditLog.Action.EXPENSE_UPDATED,
            business=self.request.business, user=self.request.user,
            resource_type="Expense", resource_id=expense.id,
        )

    def perform_destroy(self, instance):
        audit_log(
            AuditLog.Action.EXPENSE_DELETED,
            business=self.request.business, user=self.request.user,
            resource_type="Expense", resource_id=instance.id,
            old_values={"amount": str(instance.amount)},
        )
        instance.delete()
