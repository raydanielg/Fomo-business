import uuid

from django.conf import settings
from django.db import models


class HelpCategory(models.Model):
    """Guide sections — Getting Started, Sales, Inventory…"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    summary = models.CharField(max_length=255, blank=True, default="")
    icon = models.CharField(
        max_length=64, blank=True, default="",
        help_text="HugeIcon name hint, e.g. 'strokeRoundedShoppingCartAdd01'",
    )
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "help categories"

    def __str__(self):
        return self.name


class HelpArticle(models.Model):
    """A single guide. Content is markdown-lite: blank lines split
    paragraphs, '## ' starts a section, '- ' is a bullet, '1. ' a step."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(
        HelpCategory, on_delete=models.PROTECT, related_name="articles"
    )
    slug = models.SlugField(max_length=128, db_index=True)
    language = models.CharField(max_length=8, default="en", db_index=True)
    title = models.CharField(max_length=255)
    summary = models.CharField(max_length=500, blank=True, default="")
    content = models.TextField()
    status = models.CharField(
        max_length=16, choices=Status.choices,
        default=Status.DRAFT, db_index=True,
    )
    featured = models.BooleanField(default=False, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    # entitlement metadata — displayed to users, enforced by real APIs
    required_feature = models.CharField(max_length=64, blank=True, default="")
    required_permission = models.CharField(max_length=64, blank=True, default="")
    # "Try it now" deep link into the app, e.g. "/products"
    target_route = models.CharField(max_length=128, blank=True, default="")
    views = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "language"], name="uniq_help_article_slug_lang"
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.language})"


class HelpBookmark(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="help_bookmarks",
    )
    article = models.ForeignKey(
        HelpArticle, on_delete=models.CASCADE, related_name="bookmarks"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "article"], name="uniq_help_bookmark"
            ),
        ]


class HelpFeedback(models.Model):
    article = models.ForeignKey(
        HelpArticle, on_delete=models.CASCADE, related_name="feedback"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    helpful = models.BooleanField()
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)


class HelpSearchLog(models.Model):
    """Search analytics — powers popular guides and finds doc gaps."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    query = models.CharField(max_length=255)
    results_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
