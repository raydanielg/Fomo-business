import redis
from django.conf import settings
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """Liveness probe — process is up."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(exclude=True)
    def get(self, request):
        return Response({"status": "ok"})


class SupportConfigView(APIView):
    """Fomo customer-care channels — env-configurable so support details
    change without an app release. Unauthenticated on purpose."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(
            {
                "success": True,
                "data": {
                    "phone": settings.SUPPORT_PHONE,
                    "whatsapp": settings.SUPPORT_WHATSAPP,
                    "email": settings.SUPPORT_EMAIL,
                    "docs_url": settings.SUPPORT_DOCS_URL,
                    "hours": settings.SUPPORT_HOURS,
                },
            }
        )


class ReadinessCheckView(APIView):
    """Readiness probe — verifies DB and Redis connectivity."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(exclude=True)
    def get(self, request):
        checks = {"database": False, "redis": False}

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            checks["database"] = True
        except Exception:
            pass

        try:
            client = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2)
            checks["redis"] = client.ping()
        except Exception:
            pass

        healthy = all(checks.values())
        return Response(
            {"status": "ready" if healthy else "degraded", "checks": checks},
            status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        )
