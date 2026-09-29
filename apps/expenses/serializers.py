from rest_framework import serializers

from .models import Expense, ExpenseCategory


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id", "name", "is_active"]
        read_only_fields = ["id"]


class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")
    created_by_email = serializers.CharField(source="created_by.email", read_only=True, default="")

    class Meta:
        model = Expense
        fields = [
            "id", "branch", "branch_name", "category", "category_name",
            "amount", "payment_method", "description", "reference",
            "expense_date", "created_by", "created_by_email",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]
