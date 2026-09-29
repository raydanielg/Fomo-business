from rest_framework import serializers

from .models import Report, ScheduledReport


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = [
            "key", "name", "description", "category", "feature_key",
            "capabilities", "supported_filters", "minimum_access_level",
            "sort_order",
        ]


class ScheduledReportSerializer(serializers.ModelSerializer):
    report_key = serializers.CharField(source="report.key", read_only=True)
    report_name = serializers.CharField(source="report.name", read_only=True)
    recipient_ids = serializers.SerializerMethodField()
    creator_email = serializers.CharField(source="creator.email", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")

    class Meta:
        model = ScheduledReport
        fields = [
            "id", "report", "report_key", "report_name", "branch",
            "branch_name", "creator", "creator_email", "recipient_ids",
            "frequency", "day_of_week", "day_of_month", "hour", "format",
            "filters", "status", "next_run_at", "last_run_at",
            "created_at",
        ]
        read_only_fields = [
            "id", "creator", "next_run_at", "last_run_at", "created_at",
        ]

    def get_recipient_ids(self, obj):
        return [str(u.id) for u in obj.recipients.all()]


class ScheduledReportWriteSerializer(serializers.Serializer):
    report_key = serializers.CharField()
    recipient_ids = serializers.ListField(
        child=serializers.UUIDField(), min_length=1
    )
    frequency = serializers.ChoiceField(choices=ScheduledReport.Frequency.choices)
    day_of_week = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=6
    )
    day_of_month = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=28
    )
    hour = serializers.IntegerField(min_value=0, max_value=23, default=8)
    format = serializers.ChoiceField(
        choices=ScheduledReport.Format.choices, default="csv"
    )
    branch_id = serializers.UUIDField(required=False, allow_null=True)
    filters = serializers.DictField(required=False, default=dict)


class ScheduledReportPatchSerializer(serializers.Serializer):
    recipient_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False
    )
    frequency = serializers.ChoiceField(
        choices=ScheduledReport.Frequency.choices, required=False
    )
    day_of_week = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=6
    )
    day_of_month = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=28
    )
    hour = serializers.IntegerField(
        required=False, min_value=0, max_value=23
    )
    status = serializers.ChoiceField(
        choices=[ScheduledReport.Status.ACTIVE, ScheduledReport.Status.PAUSED],
        required=False,
    )
    filters = serializers.DictField(required=False)
