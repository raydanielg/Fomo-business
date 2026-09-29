from django.contrib import admin

from .models import Expense, ExpenseCategory


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "business", "is_active"]
    list_filter = ["is_active", "business"]
    search_fields = ["name"]


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ["category", "business", "branch", "amount", "expense_date"]
    list_filter = ["business", "category", "payment_method"]
    search_fields = ["description", "reference"]
    readonly_fields = ["id", "created_at", "updated_at"]
