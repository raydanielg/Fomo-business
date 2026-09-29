from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    InventoryMovementViewSet,
    StockAdjustmentView,
    StockLevelViewSet,
    StockTransferView,
)

router = DefaultRouter()
router.register("levels", StockLevelViewSet, basename="stock-level")
router.register("movements", InventoryMovementViewSet, basename="movement")

urlpatterns = [
    path("adjust/", StockAdjustmentView.as_view(), name="stock-adjust"),
    path("transfer/", StockTransferView.as_view(), name="stock-transfer"),
    path("", include(router.urls)),
]
