from django.db.models import Count, F, Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import HelpArticle, HelpBookmark, HelpCategory, HelpFeedback, HelpSearchLog
from .serializers import (
    FeedbackSerializer,
    HelpArticleDetailSerializer,
    HelpArticleListSerializer,
    HelpCategorySerializer,
)


def _lang(request):
    """Requested language with English fallback — applied per slug."""
    return request.query_params.get("lang", "en")


class HelpCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Published categories with their article counts."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = HelpCategorySerializer

    def get_queryset(self):
        return (
            HelpCategory.objects.filter(is_active=True)
            .annotate(
                _article_count=Count(
                    "articles",
                    filter=Q(articles__status=HelpArticle.Status.PUBLISHED),
                )
            )
            .filter(_article_count__gt=0)
        )


class HelpArticleViewSet(viewsets.ReadOnlyModelViewSet):
    """Guide articles. Articles exist per-language; the API prefers the
    requested language and falls back to English per slug."""

    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "slug"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return HelpArticleDetailSerializer
        return HelpArticleListSerializer

    def get_queryset(self):
        qs = HelpArticle.objects.filter(
            status=HelpArticle.Status.PUBLISHED
        ).select_related("category")

        lang = _lang(self.request)
        if lang != "en":
            # requested language where it exists, English fallback otherwise
            translated = set(
                qs.filter(language=lang).values_list("slug", flat=True)
            )
            qs = qs.filter(Q(language=lang) | (
                Q(language="en") & ~Q(slug__in=translated)
            ))
        else:
            qs = qs.filter(language="en")

        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category__key=category)
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        bookmarked_ids = set(
            HelpBookmark.objects.filter(user=request.user)
            .values_list("article_id", flat=True)
        )
        items = list(qs)
        for a in items:
            a._bookmarked = a.id in bookmarked_ids
        return Response(
            {"success": True, "data": self.get_serializer(items, many=True).data}
        )

    def retrieve(self, request, *args, **kwargs):
        article = self.get_object()
        HelpArticle.objects.filter(pk=article.pk).update(views=F("views") + 1)
        article.refresh_from_db(fields=["views"])
        return super().retrieve(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def popular(self, request):
        """Featured guides first, then most viewed — no fake metrics."""
        qs = list(self.get_queryset()[:200])
        qs.sort(key=lambda a: (not a.featured, -a.views))
        return Response(
            {"success": True, "data": HelpArticleListSerializer(qs[:8], many=True).data}
        )

    @action(detail=False, methods=["get"])
    def search(self, request):
        q = (request.query_params.get("q") or "").strip()
        if not q:
            return Response({"success": True, "data": []})
        qs = self.get_queryset().filter(
            Q(title__icontains=q)
            | Q(summary__icontains=q)
            | Q(content__icontains=q)
            | Q(category__name__icontains=q)
        )
        HelpSearchLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            query=q[:255],
            results_count=qs.count(),
        )
        return Response(
            {"success": True, "data": HelpArticleListSerializer(qs[:30], many=True).data}
        )

    @action(detail=False, methods=["get"])
    def bookmarks(self, request):
        ids = HelpBookmark.objects.filter(user=request.user).values_list(
            "article_id", flat=True
        )
        qs = self.get_queryset().filter(id__in=ids)
        items = list(qs)
        for a in items:
            a._bookmarked = True
        return Response(
            {"success": True, "data": HelpArticleListSerializer(items, many=True).data}
        )

    @action(detail=True, methods=["post"], url_path="bookmark")
    def bookmark(self, request, slug=None):
        article = self.get_object()
        obj, created = HelpBookmark.objects.get_or_create(
            user=request.user, article=article
        )
        if not created:
            obj.delete()
        return Response({"success": True, "data": {"bookmarked": created}})

    @action(detail=True, methods=["post"], url_path="feedback")
    def feedback(self, request, slug=None):
        article = self.get_object()
        s = FeedbackSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        HelpFeedback.objects.create(
            article=article,
            user=request.user,
            helpful=s.validated_data["helpful"],
            comment=s.validated_data["comment"],
        )
        return Response({"success": True, "data": {"received": True}}, status=status.HTTP_201_CREATED)
