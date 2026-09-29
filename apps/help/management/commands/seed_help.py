from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.help.models import HelpArticle, HelpCategory

CATEGORIES = [
    ("getting-started", "Getting started", "New to Fomo? Start here.", "strokeRoundedRocket01"),
    ("sales", "Sales", "Make sales and track every transaction.", "strokeRoundedShoppingCartAdd01"),
    ("products", "Products", "What your business sells.", "strokeRoundedPackage"),
    ("inventory", "Inventory", "Stock levels and movements.", "strokeRoundedContainer"),
    ("customers", "Customers", "The people who buy from you.", "strokeRoundedUserAdd01"),
    ("expenses", "Expenses", "Where your money goes.", "strokeRoundedReceiptText"),
    ("invoices", "Invoices", "Bill customers and get paid.", "strokeRoundedInvoice03"),
    ("payments", "Payments", "Money received and tracked.", "strokeRoundedWallet01"),
    ("reports", "Reports", "Understand your business numbers.", "strokeRoundedChartIncrease"),
    ("staff", "Staff & roles", "Your team and their access.", "strokeRoundedShieldUser"),
    ("branches", "Branches", "Run multiple locations.", "strokeRoundedStore01"),
    ("subscription", "Subscription", "Plans, limits and billing.", "strokeRoundedCrown"),
    ("account", "Account & settings", "Your profile, security and preferences.", "strokeRoundedSettings02"),
    ("troubleshooting", "Troubleshooting", "Fix problems fast.", "strokeRoundedHelpCircle"),
]

# (slug, category_key, title, summary, target_route, featured, required_feature, content)
ARTICLES = [
    (
        "welcome-to-fomo", "getting-started", "Welcome to Fomo",
        "What Fomo is and how it simplifies your business.",
        "", True, "",
        """Fomo is your business, simplified. It brings your sales, products, stock, customers, expenses, invoices and reports into one place, on your phone.

## How Fomo works

Everything in Fomo belongs to a business. You can run more than one business, and each business can have several branches. What each person can do is decided by their role — for example a cashier sells, while an owner sees everything.

## Where to start

- Set up your business details
- Add your first product
- Record your first sale

Your dashboard keeps today's numbers in front of you — sales, expenses and estimated profit at a glance.""",
    ),
    (
        "set-up-your-business", "getting-started", "Set up your business",
        "Business name, type, contact details and currency.",
        "/business/setup", True, "",
        """Your business profile powers everything else in Fomo.

## Before you start

You need a Fomo account and permission to create a business.

## Steps

1. Open the business setup page
2. Enter your business name and type (retail, wholesale, services…)
3. Add a phone number and email your customers can use
4. Pick your location — city and region
5. Choose your currency (TZS is the default)
6. Upload a logo so receipts look professional
7. Save

Your first branch is created automatically as the main branch. You can add more branches later from Settings, Branches.""",
    ),
    (
        "understanding-the-dashboard", "getting-started", "Understanding the dashboard",
        "What each number on your dashboard means.",
        "/home", True, "",
        """The dashboard is the heartbeat of your business.

## What you see

- Today's sales — total money in since midnight
- Expenses — what you have spent today
- Estimated profit — sales profit minus expenses
- Transactions — how many sales you have made
- The sales chart — your trend over the last days

## Needs your attention

Fomo flags things that matter: products running low on stock, overdue invoices and pending payments. Tap any of them to jump straight to the problem.

## The eye icon

Tap the eye next to your sales total to hide sensitive numbers when you are in public. Tap again to show them.""",
    ),
    (
        "make-a-sale", "sales", "How to make a sale",
        "The complete point-of-sale flow, start to finish.",
        "/pos", True, "sales.create",
        """Selling in Fomo takes seconds.

## Before you start

You need at least one product with a selling price.

## Steps

1. Open Sales and tap New sale, or use the quick action on the dashboard
2. Search or scan the product to add it to the cart
3. Adjust the quantity — tap to change
4. Pick the customer, or leave it as Walk-in Customer
5. Choose how they are paying — cash, mobile money, bank or card
6. Tap Complete sale
7. The receipt is created instantly — you can print or share it

Stock updates automatically. A product you cannot over-sell shows an error instead of failing silently.""",
    ),
    (
        "sales-history-and-receipts", "sales", "Sales history and receipts",
        "Find a past sale, view it and print its receipt.",
        "/sales", False, "",
        """Every sale is kept with its full detail.

## Viewing a sale

Open Sales and tap any transaction. You see the items, quantities, payment method, status and the receipt number.

## Printing a receipt

Tap a completed sale, then tap Print receipt. Fomo builds a professional PDF — preview it, then print or share it.

## Statuses

- Paid — the sale is complete
- Pending — payment is still expected
- Cancelled — the sale was voided and stock was returned""",
    ),
    (
        "add-a-product", "products", "How to add a product",
        "Name, SKU, prices and starting stock.",
        "/products", True, "products.manage",
        """Products are the items or services your business sells.

## Before you start

You need permission to manage products.

## Steps

1. Open Products and tap Add product
2. Enter the product name
3. Add an SKU — a short unique code so products never mix up
4. Pick a category so reports group correctly
5. Set the buying price — what it costs you
6. Set the selling price — what customers pay
7. Enter the opening stock and a low-stock threshold so Fomo can warn you
8. Save

## Tips

- The profit per unit is shown on the product page
- Set a low-stock threshold so you never run out silently""",
    ),
    (
        "product-detail-page", "products", "The product detail page",
        "Trends, stock per branch, editing and deleting.",
        "/products", False, "",
        """Tap any product to open its detail page.

## What you see

- Cost, selling price and profit per unit
- A sales trend chart — how this product has sold recently
- Stock per branch
- How much it has sold this month versus last month

## Editing and deleting

If your role allows it, you can edit details or delete the product from this page. Owners and managers can; cashiers cannot.""",
    ),
    (
        "stock-levels-and-movements", "inventory", "Stock levels and movements",
        "Green in stock, amber low, red out — and why stock changed.",
        "/inventory", True, "",
        """Inventory shows what is on your shelves right now.

## Stock levels

Each product shows a colour:

- Green — in stock
- Amber — running low, below its threshold
- Red — out of stock

## Movements

Every change is logged: sales subtract stock, purchases add it, and manual adjustments are recorded with a reason. Open the Movements tab to see the full history — who changed what, when and why.

## Low stock alerts

The Low stock tab lists products under their threshold. Tap one to open the product and restock.""",
    ),
    (
        "manage-customers", "customers", "Managing customers",
        "Add, import, call and track what customers owe.",
        "/customers", True, "",
        """Customers let you track who buys from you and who owes you money.

## Adding customers

Open Customers and tap Add customer. Or import straight from your phone's contacts — Fomo fills the name and phone for you.

## Walk-in Customer

Every business has a Walk-in Customer for quick counter sales where you do not need a name.

## Customer details

Tap a customer to see their phone, email and balance — what they owe you. You can call them or save them to your contacts from there.""",
    ),
    (
        "record-an-expense", "expenses", "How to record an expense",
        "Keep your profit honest by tracking every cost.",
        "/expenses", True, "expenses.manage",
        """Rent, transport, supplies — every cost counts against profit.

## Steps

1. Open Expenses and tap Add expense
2. Say what it was for
3. Pick a category so spending groups correctly
4. Pick the branch
5. Enter the amount and how you paid
6. Save

## Why it matters

Your dashboard's estimated profit subtracts today's expenses. Skip expenses and your profit looks better than it is. Tap any expense to see its full details, including who recorded it.""",
    ),
    (
        "invoices-and-balances", "invoices", "Invoices and balances",
        "Bill a customer and track what is owed.",
        "/invoices", False, "",
        """An invoice is a formal bill for a customer.

## Creating an invoice

Invoices are created for sales that are not fully paid at the counter. Each one carries the customer, the items, the total, what has been paid and the balance left.

## Statuses

- Sent — delivered to the customer, awaiting payment
- Partial — some of it has been paid
- Paid — fully settled
- Overdue — past its due date, and flagged on your dashboard

## Collecting payment

Open the invoice and record a payment against it. The balance updates immediately and the payment lands in your Payments list.""",
    ),
    (
        "understanding-payments", "payments", "Understanding payments",
        "How money received is tracked per method.",
        "/payments", False, "",
        """The Payments page is your cash drawer — every shilling received is here.

## What each row shows

The payment method, who paid, when, and how much. Completed payments are green; refunded payments show in blue with a minus.

## Details

Tap a payment for the full record — method, customer, reference number, which sale or invoice it belongs to, and who received it.

## Statuses

- Completed — money received
- Pending — awaiting confirmation
- Failed — did not go through
- Refunded — returned to the customer""",
    ),
    (
        "reading-reports", "reports", "Reading your reports",
        "Sales, profit, stock and more — all entitlement-aware.",
        "/reports", True, "",
        """Reports turn your daily activity into answers.

## What's inside

- Sales reports — revenue over time, top products
- Profit reports — what you really made after costs
- Inventory reports — what your stock is worth
- Customer and payment reports — who buys and who owes

## Date ranges

Tap the period picker on any report — today, this week, this month or a custom range from the calendar.

## Plan limits

Some reports belong to higher plans. Locked reports show an upgrade prompt instead of pretending they work — your plan decides what you see.""",
    ),
    (
        "inviting-staff", "staff", "Inviting and managing staff",
        "Roles decide exactly what each member can do.",
        "/staff", False, "staff.manage",
        """Your team joins by email invite and sets their own password.

## Steps

1. Open Staff and tap Invite
2. Enter their name, email and role
3. Send — they get an email to join

## Roles and permissions

Each role controls what a member can see and do. A cashier sells but cannot see profit reports. An owner sees everything. You never need to share your own login.

## Suspending someone

Tap a member and suspend them — they lose access instantly. Reactivate them the same way when they return.""",
    ),
    (
        "manage-branches", "branches", "Managing branches",
        "One business, many locations.",
        "/branches", False, "",
        """Each branch tracks its own stock, sales and staff.

## Adding a branch

Open Settings, Branches and tap Add branch. Give it a name and location.

## The main branch

Your first branch is the default — it powers POS and reports when nothing else is selected.

## Keeping control

You can edit a branch's details or deactivate one you no longer use. Deactivating keeps all its records but stops new sales.""",
    ),
    (
        "plans-and-limits", "subscription", "Plans and limits",
        "What your plan includes and how to upgrade.",
        "/subscription", False, "",
        """Your plan decides which features and reports you can use.

## Checking your plan

Open Subscription to see your current plan, when it renews, and how much of each limit you have used this month.

## Usage meters

The meters turn amber when you pass 70% of a limit and red at 90% — you get warned before you hit a wall.

## Upgrading

Switch plans from the same page and your new limits apply immediately. If your plan allows it, you will see a Switch button on each plan card.""",
    ),
    (
        "your-profile-and-security", "account", "Your profile and security",
        "Photo, details and password.",
        "/profile", False, "",
        """## Your profile

Open Profile to add your photo — tap the camera badge to take a selfie or pick from your gallery. Your photo appears in the header and the side drawer.

## Changing your password

From Profile, tap Change password. Pick a new password and confirm it — Fomo signs out your other sessions automatically, so a stolen session dies with it.

## Language and theme

From Settings you can switch the app between English and Kiswahili, and choose Light, Dark or System theme.""",
    ),
    (
        "notifications", "account", "Notifications",
        "Never miss low stock or an overdue invoice.",
        "/notifications", False, "",
        """The bell in the header shows your unread count.

## What's inside

Sales confirmations, low-stock warnings, overdue invoices and staff events — grouped by day in a timeline.

## Reading them

Tap a notification to open its full message — it marks itself as read. Use the check button in the header to mark everything as read at once.""",
    ),
    (
        "cant-log-in", "troubleshooting", "I can't log in",
        "The common causes and how to fix them.",
        "", True, "",
        """## Possible causes

- Incorrect email or password
- No internet connection
- Your account was suspended by your business owner

## Try this

1. Check your internet — open a web page to be sure
2. Re-check your email and password
3. Wait a moment and try again — the server may be waking up
4. If a coworker's account was suspended, they need the owner to reactivate it from Staff

Still stuck? Use the contact channels on the Help and support page.""",
    ),
    (
        "something-looks-wrong", "troubleshooting", "Data looks wrong or missing",
        "When numbers or lists look off.",
        "", False, "",
        """## Common causes

- You are looking at the wrong business — check the business name in the side drawer
- A filter is hiding what you expect — clear search and filters
- Your role does not include that feature — some pages hide items your role cannot use

## Try this

1. Pull down to refresh the list
2. Switch business from Settings, Switch business
3. Ask your owner or manager to check your role under Staff

If a feature is locked by your plan, the Subscription page shows which plan unlocks it.""",
    ),
]


class Command(BaseCommand):
    help = "Seed the Help Center with starter categories and guides (en)."

    def handle(self, *args, **options):
        cats = {}
        for i, (key, name, summary, icon) in enumerate(CATEGORIES):
            cats[key], _ = HelpCategory.objects.update_or_create(
                key=key,
                defaults={
                    "name": name,
                    "summary": summary,
                    "icon": icon,
                    "sort_order": i,
                    "is_active": True,
                },
            )

        created = updated = 0
        for i, (slug, cat, title, summary, route, featured, feature, content) in enumerate(
            ARTICLES
        ):
            _, was_created = HelpArticle.objects.update_or_create(
                slug=slug,
                language="en",
                defaults={
                    "category": cats[cat],
                    "title": title,
                    "summary": summary,
                    "content": content.strip(),
                    "status": HelpArticle.Status.PUBLISHED,
                    "featured": featured,
                    "sort_order": i,
                    "required_feature": feature,
                    "target_route": route,
                    "published_at": timezone.now(),
                },
            )
            created += was_created
            updated += not was_created

        self.stdout.write(
            self.style.SUCCESS(
                f"Help seeded: {len(cats)} categories, "
                f"{created} articles created, {updated} updated."
            )
        )
