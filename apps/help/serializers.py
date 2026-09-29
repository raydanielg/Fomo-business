from rest_framework import serializers

from .models import HelpArticle, HelpCategory


class HelpCategorySerializer(serializers.ModelSerializer):
    article_count = serializers.SerializerMethodField()

    class Meta:
        model = HelpCategory
        fields = ["id", "key", "name", "summary", "icon", "sort_order", "article_count"]

    def get_article_count(self, obj):
        return getattr(obj, "_article_count", obj.articles.filter(
            status=HelpArticle.Status.PUBLISHED
        ).count())


class HelpArticleListSerializer(serializers.ModelSerializer):
    category_key = serializers.CharField(source="category.key", read_only=True)
    bookmarked = serializers.SerializerMethodField()

    class Meta:
        model = HelpArticle
        fields = [
            "id", "slug", "title", "summary", "category_key",
            "featured", "required_feature", "required_permission",
            "target_route", "views", "bookmarked", "published_at",
        ]

    def get_bookmarked(self, obj):
        return getattr(obj, "_bookmarked", False)


class HelpArticleDetailSerializer(HelpArticleListSerializer):
    class Meta(HelpArticleListSerializer.Meta):
        fields = HelpArticleListSerializer.Meta.fields + [
            "content", "language", "status",
        ]


class FeedbackSerializer(serializers.Serializer):
    helpful = serializers.BooleanField()
    comment = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=2000
    )
