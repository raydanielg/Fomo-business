from django.contrib import admin

from .models import (
    HelpArticle,
    HelpBookmark,
    HelpCategory,
    HelpFeedback,
    HelpSearchLog,
)


@admin.register(HelpCategory)
class HelpCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "key", "sort_order", "is_active"]
    list_editable = ["sort_order", "is_active"]
    prepopulated_fields = {"key": ("name",)}


@admin.register(HelpArticle)
class HelpArticleAdmin(admin.ModelAdmin):
    list_display = [
        "title", "slug", "language", "category",
        "status", "featured", "views", "published_at",
    ]
    list_filter = ["status", "language", "category", "featured"]
    list_editable = ["status", "featured"]
    search_fields = ["title", "summary", "content"]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ["id", "views", "created_at", "updated_at"]


@admin.register(HelpFeedback)
class HelpFeedbackAdmin(admin.ModelAdmin):
    list_display = ["article", "user", "helpful", "created_at"]
    list_filter = ["helpful"]
    readonly_fields = ["article", "user", "helpful", "comment", "created_at"]


@admin.register(HelpBookmark)
class HelpBookmarkAdmin(admin.ModelAdmin):
    list_display = ["user", "article", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(HelpSearchLog)
class HelpSearchLogAdmin(admin.ModelAdmin):
    list_display = ["query", "results_count", "user", "created_at"]
    readonly_fields = ["query", "results_count", "user", "created_at"]
