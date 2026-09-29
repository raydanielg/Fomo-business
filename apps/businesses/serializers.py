from rest_framework import serializers

from .models import Business


class BusinessCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = [
            "name",
            "business_type",
            "registration_number",
            "tax_number",
            "phone",
            "email",
            "address",
            "city",
            "region",
            "country",
            "currency",
            "timezone",
            "logo",
        ]


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = [
            "id",
            "name",
            "slug",
            "business_type",
            "registration_number",
            "tax_number",
            "phone",
            "email",
            "address",
            "city",
            "region",
            "country",
            "currency",
            "timezone",
            "logo",
            "status",
            "allow_negative_stock",
            "settings",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "status", "created_at", "updated_at"]


class BusinessUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = [
            "name",
            "business_type",
            "registration_number",
            "tax_number",
            "phone",
            "email",
            "address",
            "city",
            "region",
            "country",
            "currency",
            "timezone",
            "logo",
            "allow_negative_stock",
            "settings",
        ]
