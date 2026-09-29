from rest_framework.routers import DefaultRouter

from .views import HelpArticleViewSet, HelpCategoryViewSet

router = DefaultRouter()
router.register("categories", HelpCategoryViewSet, basename="help-category")
router.register("articles", HelpArticleViewSet, basename="help-article")

urlpatterns = router.urls
