from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import AuthToken, DeviceSession, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["-created_at"]
    list_display = ["email", "first_name", "last_name", "is_active", "is_verified", "is_staff", "date_joined"]
    list_filter = ["is_active", "is_verified", "is_staff"]
    search_fields = ["email", "first_name", "last_name", "phone"]
    readonly_fields = ["id", "date_joined", "last_login", "created_at", "updated_at"]
    fieldsets = (
        (None, {"fields": ("id", "email", "password")}),
        ("Personal", {"fields": ("first_name", "last_name", "phone", "avatar")}),
        ("Status", {"fields": ("is_active", "is_verified", "is_staff", "is_superuser", "deletion_requested_at")}),
        ("Dates", {"fields": ("date_joined", "last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2"),
        }),
    )


@admin.register(AuthToken)
class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "purpose", "expires_at", "used_at", "created_at"]
    list_filter = ["purpose"]
    search_fields = ["user__email"]
    readonly_fields = ["id", "token", "created_at"]


@admin.register(DeviceSession)
class DeviceSessionAdmin(admin.ModelAdmin):
    list_display = ["user", "device_name", "ip_address", "last_seen_at", "revoked_at"]
    list_filter = ["revoked_at"]
    search_fields = ["user__email", "device_name"]
    readonly_fields = ["id", "refresh_jti", "created_at"]
