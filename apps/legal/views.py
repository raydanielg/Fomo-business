from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import LegalDocument, LegalAcceptance
from .serializers import LegalDocumentSerializer


def _current(doc_type):
    return (
        LegalDocument.objects.filter(doc_type=doc_type, is_current=True)
        .order_by("-effective_date")
        .first()
    )


class LegalDocumentView(APIView):
    """GET /legal/<doc_type>/ — current version of a legal document."""

    permission_classes = [AllowAny]

    def get(self, request, doc_type):
        doc = _current(doc_type)
        if doc is None:
            return Response(
                {"detail": "Document unavailable."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(LegalDocumentSerializer(
            doc, context={"request": request}).data)


class LegalAcceptView(APIView):
    """POST /legal/<doc_type>/accept — record acceptance of current version."""

    permission_classes = [IsAuthenticated]

    def post(self, request, doc_type):
        doc = _current(doc_type)
        if doc is None:
            return Response(
                {"detail": "Document unavailable."},
                status=status.HTTP_404_NOT_FOUND,
            )
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or \
            request.META.get("REMOTE_ADDR")
        LegalAcceptance.objects.get_or_create(
            user=request.user,
            document=doc,
            defaults={
                "ip_address": ip or None,
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
            },
        )
        return Response(
            {"detail": "Accepted.", "version": doc.version},
            status=status.HTTP_201_CREATED,
        )
