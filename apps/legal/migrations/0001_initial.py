# Generated for Fomo legal module
import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LegalDocument",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("doc_type", models.CharField(choices=[("terms", "Terms of Service"), ("privacy", "Privacy Policy")], max_length=20)),
                ("title", models.CharField(max_length=200)),
                ("version", models.CharField(max_length=20)),
                ("content", models.TextField(help_text="Markdown-ish: '## ' headings, '- ' bullets.")),
                ("effective_date", models.DateField()),
                ("is_current", models.BooleanField(default=True)),
                ("requires_acceptance", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["doc_type", "-effective_date"], "unique_together": {("doc_type", "version")}},
        ),
        migrations.CreateModel(
            name="LegalAcceptance",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("accepted_at", models.DateTimeField(auto_now_add=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, default="")),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="acceptances", to="legal.legaldocument")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="legal_acceptances", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-accepted_at"], "unique_together": {("user", "document")}},
        ),
    ]
