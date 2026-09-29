from django.contrib import admin

from .models import EntitlementEvent, Report, ReportUsage, ScheduledReport


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["key", "name", "category", "feature_key",
                    "minimum_access_level", "is_active", "sort_order"]
    list_filter = ["category", "is_active", "minimum_access_level"]
    search_fields = ["key", "name"]


class ScheduledReportRecipientsInline(admin.TabularInline):
    model = ScheduledReport.recipients.through
    extra = 0
    verbose_name = "recipient"
    verbose_name_plural = "recipients"


@admin.register(ScheduledReport)
class ScheduledReportAdmin(admin.ModelAdmin):
    list_display = ["report", "business", "creator", "frequency",
                    "format", "status", "next_run_at", "last_run_at"]
    list_filter = ["status", "frequency", "format"]
    search_fields = ["report__key", "business__name", "creator__email"]
    readonly_fields = ["last_run_at"]
    exclude = ["recipients"]
    inlines = [ScheduledReportRecipientsInline]


@admin.register(ReportUsage)
class ReportUsageAdmin(admin.ModelAdmin):
    list_display = ["business", "report_key", "action", "format",
                    "row_count", "user", "created_at"]
    list_filter = ["action", "format", "created_at"]
    search_fields = ["business__name", "report_key", "user__email"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(EntitlementEvent)
class EntitlementEventAdmin(admin.ModelAdmin):
    list_display = ["business", "event_type", "feature_key", "report_key",
                    "reason", "user", "created_at"]
    list_filter = ["event_type", "reason", "created_at"]
    search_fields = ["business__name", "feature_key", "report_key",
                     "user__email"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
