"""Idempotent setup of Celery Beat periodic tasks (DatabaseScheduler)."""

from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Register periodic tasks in django-celery-beat (idempotent)."

    def handle(self, *args, **options):
        daily_6am, _ = CrontabSchedule.objects.get_or_create(
            minute="0", hour="6", timezone="Africa/Dar_es_Salaam"
        )
        hourly, _ = CrontabSchedule.objects.get_or_create(
            minute="0", timezone="Africa/Dar_es_Salaam"
        )
        every_15m, _ = CrontabSchedule.objects.get_or_create(
            minute="*/15", timezone="Africa/Dar_es_Salaam"
        )

        tasks = [
            ("Overdue invoices", "apps.notifications.tasks.check_overdue_invoices", daily_6am),
            ("Expire subscriptions", "apps.notifications.tasks.expire_subscriptions", daily_6am),
            ("Aggregate usage", "apps.notifications.tasks.aggregate_usage", daily_6am),
            ("Low stock check", "apps.notifications.tasks.check_low_stock", hourly),
            ("Scheduled reports", "apps.notifications.tasks.run_due_scheduled_reports", every_15m),
        ]
        for name, task, schedule in tasks:
            _, created = PeriodicTask.objects.get_or_create(
                name=name,
                defaults={"task": task, "crontab": schedule},
            )
            if created:
                self.stdout.write(f"  + {name}")
            else:
                self.stdout.write(f"  = {name} (exists)")
        self.stdout.write(self.style.SUCCESS("Periodic tasks registered."))
