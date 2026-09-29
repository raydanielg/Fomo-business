from django.contrib import admin

from .models import Membership


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "business", "role", "status", "joined_at"]
    list_filter = ["status", "role__code"]
    search_fields = ["user__email", "business__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    filter_horizontal = ["allowed_branches"]
