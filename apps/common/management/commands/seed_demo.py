"""Development seed — NEVER run in production.

Rich demo dataset for owner@demo.fomo: products across categories,
customers, suppliers, ~30 days of sales, expenses, an invoice with a
partial payment and notifications — so every screen shows real data.
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Seed demo data: business, users, catalog, sales, expenses."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo is disabled when DEBUG=False.")

        from apps.accounts.models import User
        from apps.customers.models import Customer
        from apps.expenses.models import Expense, ExpenseCategory
        from apps.inventory.services import adjust_stock
        from apps.invoices.services import create_invoice, issue_invoice
        from apps.notifications.services import notify
        from apps.payments.services import record_payment
        from apps.products.models import Category, Product, Unit
        from apps.sales.services import create_sale
        from apps.subscriptions.services import seed_default_plans
        from apps.suppliers.models import Supplier

        rng = random.Random(42)
        seed_default_plans()

        owner, _ = User.objects.get_or_create(
            email="owner@demo.fomo",
            defaults={
                "first_name": "Demo",
                "last_name": "Owner",
                "is_verified": True,
            },
        )
        owner.set_password("DemoPass123!")
        owner.save()

        from apps.businesses.services import create_business

        business = owner.owned_businesses.filter(name="Demo Shop").first()
        if business is None:
            business = create_business(
                owner=owner, name="Demo Shop", business_type="retail",
                phone="+255700000000", email="demo@fomo.app",
                city="Dar es Salaam",
            )
        branch = business.branch_set.first()

        # ── catalog ────────────────────────────────────────────────────
        unit, _ = Unit.objects.get_or_create(
            business=business, abbreviation="pcs", defaults={"name": "Pieces"}
        )

        cats = {}
        for name in ["Beverages", "Food", "Household", "Personal Care"]:
            cats[name], _ = Category.objects.get_or_create(
                business=business, name=name
            )

        catalog = [
            # (name, cat, buy, sell, stock, threshold)
            ("Coca-Cola 500ml", "Beverages", 800, 1200, 240, 30),
            ("Fanta Orange 500ml", "Beverages", 800, 1200, 180, 30),
            ("Bottled Water 1.5L", "Beverages", 700, 1000, 320, 40),
            ("Energy Drink", "Beverages", 2500, 3500, 60, 15),
            ("Fresh Milk 1L", "Beverages", 2200, 2800, 40, 20),
            ("White Bread", "Food", 1000, 1500, 85, 20),
            ("Rice 1kg", "Food", 2500, 3200, 150, 30),
            ("Cooking Oil 1L", "Food", 5000, 6500, 90, 20),
            ("Sugar 1kg", "Food", 2800, 3500, 110, 25),
            ("Wheat Flour 2kg", "Food", 4200, 5500, 65, 15),
            ("Laundry Soap Bar", "Household", 1200, 1800, 200, 40),
            ("Dish Soap 500ml", "Household", 1800, 2500, 75, 20),
            ("Tissue Roll 4pk", "Household", 2000, 2800, 120, 25),
            ("Bath Soap", "Personal Care", 1500, 2200, 8, 20),      # low
            ("Toothpaste 150g", "Personal Care", 2500, 3500, 5, 15),  # low
            ("Body Lotion 400ml", "Personal Care", 6000, 8500, 0, 10),  # out
        ]
        products = []
        for i, (name, cat, buy, sell, stock, thresh) in enumerate(catalog, 1):
            p, _ = Product.objects.get_or_create(
                business=business, sku=f"SKU-{i:04d}",
                defaults={
                    "name": name, "category": cats[cat], "unit": unit,
                    "buying_price": buy, "selling_price": sell,
                    "cost_price": buy, "low_stock_threshold": thresh,
                },
            )
            products.append(p)
            if stock:
                adjust_stock(
                    business=business, branch=branch, product=p,
                    quantity=stock, direction="in",
                    note="Initial stock", user=owner,
                )

        # ── customers ──────────────────────────────────────────────────
        walkin, _ = Customer.objects.get_or_create(
            business=business, phone="+255711111111",
            defaults={"name": "Walk-in Customer"},
        )
        customers = [walkin]
        for name, phone, email in [
            ("Amina Juma", "+255712000001", "amina.j@example.com"),
            ("Baraka Mushi", "+255712000002", "baraka.m@example.com"),
            ("Neema Kibona", "+255712000003", "neema.k@example.com"),
            ("Joseph Lyimo", "+255712000004", ""),
            ("Fatma Said", "+255712000005", "fatma.s@example.com"),
            ("Godwin Massawe", "+255712000006", ""),
        ]:
            c, _ = Customer.objects.get_or_create(
                business=business, phone=phone,
                defaults={
                    "name": name, "email": email,
                    "created_by": owner,
                },
            )
            customers.append(c)

        # ── suppliers ──────────────────────────────────────────────────
        for name, phone in [
            ("Azam Distributors", "+255700111001"),
            ("Mohammed Enterprises", "+255700111002"),
            ("Serengeti Breweries Ltd", "+255700111003"),
        ]:
            Supplier.objects.get_or_create(
                business=business, name=name,
                defaults={"phone": phone, "created_by": owner},
            )

        # ── expenses across the month ──────────────────────────────────
        expense_cats = {}
        for name in ["Rent", "Utilities", "Transport", "Supplies"]:
            expense_cats[name], _ = ExpenseCategory.objects.get_or_create(
                business=business, name=name
            )
        expense_rows = [
            ("Monthly shop rent", "Rent", 500000, 12),
            ("Electricity bill", "Utilities", 85000, 10),
            ("Water bill", "Utilities", 32000, 10),
            ("Stock transport", "Transport", 45000, 9),
            ("Stock transport", "Transport", 40000, 2),
            ("Packaging bags", "Supplies", 25000, 7),
            ("Cleaning supplies", "Supplies", 18000, 4),
        ]
        for desc, cat, amount, days_ago in expense_rows:
            exp, created = Expense.objects.get_or_create(
                business=business, branch=branch,
                category=expense_cats[cat], description=desc,
                defaults={
                    "amount": Decimal(amount), "created_by": owner,
                    "payment_method": rng.choice(
                        ["CASH", "MOBILE_MONEY", "BANK"]
                    ),
                },
            )
            if created:
                exp.expense_date = timezone.localdate() - timedelta(
                    days=days_ago
                )
                exp.save(update_fields=["expense_date"])

        # ── sales spread over the last 30 days ─────────────────────────
        methods = ["CASH", "CASH", "CASH", "MOBILE_MONEY", "MOBILE_MONEY",
                   "CARD", "BANK"]
        # only high-stock items sell — the low/out items stay as real
        # low-stock fixtures for the demo dashboards
        sellable = [
            p for p in products
            if p.name not in ("Body Lotion 400ml", "Toothpaste 150g",
                              "Bath Soap")
        ]
        from apps.common.exceptions import APIError

        for days_ago in range(30, 0, -1):
            n_sales = rng.choices([0, 1, 2, 3, 4], weights=[15, 30, 30, 20, 5])[0]
            for _ in range(n_sales):
                picks = rng.sample(sellable, k=min(rng.randint(1, 4), 13))
                items = [
                    {"product_id": p.id, "quantity": rng.randint(1, 3)}
                    for p in picks
                ]
                total = sum(
                    p.selling_price * i["quantity"]
                    for p, i in zip(picks, items)
                )
                try:
                    sale = create_sale(
                        business=business, branch=branch, user=owner,
                        items_data=items,
                        customer=rng.choice(customers),
                        payment={
                            "method": rng.choice(methods),
                            "amount": str(total),
                        },
                    )
                except APIError:
                    continue  # stock ran out on a high-volume day
                when = timezone.now() - timedelta(
                    days=days_ago, hours=rng.randint(0, 10),
                    minutes=rng.randint(0, 59),
                )
                sale.__class__.objects.filter(pk=sale.pk).update(
                    created_at=when
                )
                sale.payments.update(paid_at=when, created_at=when)

        # ── one issued invoice with a partial payment ──────────────────
        invoice = create_invoice(
            business=business, branch=branch, user=owner,
            items_data=[
                {
                    "product_id": sellable[2].id,
                    "quantity": 5,
                    "unit_price": sellable[2].selling_price,
                },
                {
                    "product_id": sellable[6].id,
                    "quantity": 3,
                    "unit_price": sellable[6].selling_price,
                },
            ],
            customer=customers[1],
            due_date=timezone.localdate() + timedelta(days=14),
            notes="Monthly supply order",
        )
        issue_invoice(invoice=invoice, user=owner)
        record_payment(
            business=business, invoice=invoice, amount=Decimal("10000"),
            method="MOBILE_MONEY", received_by=owner,
        )

        # ── notifications for the owner ────────────────────────────────
        notify(
            owner, business=business, type="low_stock",
            title="3 products running low",
            message="Bath Soap, Toothpaste and Body Lotion are below "
                    "threshold or out of stock.",
            data={"count": 3},
        )
        notify(
            owner, business=business, type="system",
            title="Welcome to Fomo",
            message="Your business is set up. Explore the dashboard, "
                    "sales and reports — everything here is real data.",
            data={},
        )

        self.stdout.write(self.style.SUCCESS(
            f"Demo seeded. Login: owner@demo.fomo / DemoPass123! "
            f"(business_id={business.id})"
        ))
