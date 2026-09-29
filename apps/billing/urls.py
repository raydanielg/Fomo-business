from django.urls import path

from . import views

urlpatterns = [
    # webhook receiver (public, HMAC-verified)
    path("webhooks/snippe/", views.snippe_webhook, name="snippe-webhook"),

    # tenant-facing: pay for a plan via provider push
    path("checkout/pay/", views.SubscriptionPayView.as_view(), name="billing-checkout-pay"),

    # admin billing console
    path("admin/overview/", views.BillingOverviewView.as_view(), name="billing-overview"),
    path("admin/payments/", views.AdminPaymentsView.as_view(), name="admin-payments"),
    path("admin/payments/<uuid:pk>/", views.AdminPaymentDetailView.as_view(), name="admin-payment-detail"),
    path("admin/checkout-sessions/", views.AdminCheckoutSessionsView.as_view(), name="admin-sessions"),
    path("admin/payment-links/", views.AdminPaymentLinksView.as_view(), name="admin-payment-links"),
    path("admin/payouts/", views.AdminPayoutsView.as_view(), name="admin-payouts"),
    path("admin/refunds/", views.AdminRefundsView.as_view(), name="admin-refunds"),
    path("admin/payment-events/", views.AdminPaymentEventsView.as_view(), name="admin-payment-events"),
    path("admin/webhooks/", views.AdminWebhooksView.as_view(), name="admin-webhooks"),
    path("admin/reconciliation/", views.AdminReconciliationView.as_view(), name="admin-reconciliation"),
    path("admin/subscriptions/", views.AdminSubscriptionsView.as_view(), name="admin-subscriptions"),
    path("admin/invoices/", views.AdminInvoicesView.as_view(), name="admin-invoices"),
    path("admin/payment-providers/", views.AdminProvidersView.as_view(), name="admin-providers"),
    path("admin/payment-providers/snippe/health/", views.SnippeHealthView.as_view(), name="snippe-health"),
    path("admin/payment-providers/snippe/balance/", views.SnippeBalanceView.as_view(), name="snippe-balance"),
]
