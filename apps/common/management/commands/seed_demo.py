"""Development seed — NEVER run in production."""

from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Seed demo data: business, users, products, customers, a sale."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo is disabled when DEBUG=False.")

        from apps.accounts.models import User
        from apps.branches.models import Branch
        from apps.businesses.services import create_business
        from apps.customers.models import Customer
        from apps.expenses.models import Expense, ExpenseCategory
        from apps.inventory.services import adjust_stock
        from apps.products.models import Category, Product, Unit
        from apps.sales.services import create_sale
        from apps.subscriptions.services import seed_default_plans

        seed_default_plans()

        owner, _ = User.objects.get_or_create(
            email="owner@demo.fomo",
            defaults={"first_name": "Demo", "last_name": "Owner", "is_verified": True},
        )
        owner.set_password("DemoPass123!")
        owner.save()

        business = owner.owned_businesses.filter(name="Demo Shop").first()
        if business is None:
            business = create_business(
                owner=owner, name="Demo Shop", business_type="retail",
                phone="+255700000000", email="demo@fomo.app",
                city="Dar es Salaam",
            )
        branch = business.branch_set.first()

        unit, _ = Unit.objects.get_or_create(
            business=business, abbreviation="pcs", defaults={"name": "Pieces"}
        )
        cat, _ = Category.objects.get_or_create(
            business=business, name="General"
        )
        products = []
        for i, (name, buy, sell) in enumerate(
            [("Soda", 800, 1200), ("Bread", 1000, 1500), ("Rice 1kg", 2500, 3200),
             ("Cooking Oil", 5000, 6500), ("Soap", 1200, 1800)],
            start=1,
        ):
            p, _ = Product.objects.get_or_create(
                business=business, sku=f"SKU-{i:04d}",
                defaults={
                    "name": name, "category": cat, "unit": unit,
                    "buying_price": buy, "selling_price": sell,
                    "cost_price": buy, "low_stock_threshold": 10,
                },
            )
            products.append(p)
            adjust_stock(
                business=business, branch=branch, product=p,
                quantity=100, direction="in", note="Initial seed", user=owner,
            )

        customer, _ = Customer.objects.get_or_create(
            business=business, phone="+255711111111",
            defaults={"name": "Walk-in Customer"},
        )

        ec, _ = ExpenseCategory.objects.get_or_create(
            business=business, name="Rent"
        )
        Expense.objects.get_or_create(
            business=business, branch=branch, category=ec,
            description="Monthly rent",
            defaults={"amount": Decimal("500000"), "created_by": owner},
        )

        create_sale(
            business=business, branch=branch, user=owner,
            items_data=[
                {"product_id": products[0].id, "quantity": 2},
                {"product_id": products[1].id, "quantity": 1},
            ],
            customer=customer,
            payment={"method": "CASH", "amount": "3900"},
        )

        self.stdout.write(self.style.SUCCESS(
            f"Demo seeded. Login: owner@demo.fomo / DemoPass123! "
            f"(business_id={business.id})"
        ))
