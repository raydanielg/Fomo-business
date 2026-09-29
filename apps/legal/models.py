import uuid

from django.conf import settings
from django.db import models


class LegalDocumentType(models.TextChoices):
    TERMS = "terms", "Terms of Service"
    PRIVACY = "privacy", "Privacy Policy"


class LegalDocument(models.Model):
    """Versioned legal documents. Admin-editable — never hardcode in clients."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doc_type = models.CharField(max_length=20, choices=LegalDocumentType.choices)
    title = models.CharField(max_length=200)
    version = models.CharField(max_length=20)
    content = models.TextField(help_text="Markdown-ish: '## ' headings, '- ' bullets.")
    effective_date = models.DateField()
    is_current = models.BooleanField(default=True)
    requires_acceptance = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["doc_type", "-effective_date"]
        unique_together = ("doc_type", "version")

    def __str__(self):
        return f"{self.title} v{self.version}"


class LegalAcceptance(models.Model):
    """Authoritative record of a user accepting a document version."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="legal_acceptances",
    )
    document = models.ForeignKey(
        LegalDocument, on_delete=models.PROTECT, related_name="acceptances"
    )
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")

    class Meta:
        unique_together = ("user", "document")
        ordering = ["-accepted_at"]

    def __str__(self):
        return f"{self.user_id} accepted {self.document.doc_type} {self.document.version}"
