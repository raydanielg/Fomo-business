from rest_framework import serializers

from .models import LegalDocument


class LegalDocumentSerializer(serializers.ModelSerializer):
    last_updated = serializers.DateTimeField(source="updated_at")
    accepted = serializers.SerializerMethodField()

    class Meta:
        model = LegalDocument
        fields = [
            "doc_type", "title", "version", "content", "effective_date",
            "last_updated", "requires_acceptance", "accepted",
        ]

    def get_accepted(self, obj):
        user = self.context["request"].user
        if not user.is_authenticated:
            return False
        return obj.acceptances.filter(user=user).exists()
