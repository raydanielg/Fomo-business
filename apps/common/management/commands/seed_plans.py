from django.core.management.base import BaseCommand

from apps.subscriptions.services import seed_default_plans


class Command(BaseCommand):
    help = "Create/update the default subscription plans (FREE → ENTERPRISE)."

    def handle(self, *args, **options):
        seed_default_plans()
        self.stdout.write(self.style.SUCCESS("Default plans seeded."))
