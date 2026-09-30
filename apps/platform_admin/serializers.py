from rest_framework import serializers

from apps.audit.models import AuditLog
from apps.businesses.models import Business
from apps.memberships.models import Membership
from apps.notifications.models import Notification
from apps.accounts.models import User


class AdminUserSerializer(serializers.ModelSerializer):
    businesses = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "phone", "first_name", "last_name", "full_name",
            "avatar", "is_active", "is_verified", "is_staff", "is_superuser",
            "date_joined", "last_login", "businesses", "roles",
        ]

    def get_businesses(self, obj):
        return [
            {"id": str(m.business_id), "name": m.business.name, "status": m.business.status}
            for m in obj.memberships.select_related("business")[:10]
        ]

    def get_roles(self, obj):
        return [m.role.code for m in obj.memberships.select_related("role")[:10]]


class AdminMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    role_code = serializers.CharField(source="role.code", read_only=True)
    business_name = serializers.CharField(source="business.name", read_only=True)

    class Meta:
        model = Membership
        fields = [
            "id", "user_email", "user_name", "business_name",
            "role_code", "status", "joined_at", "created_at",
        ]


class AdminBusinessSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    owner_name = serializers.CharField(source="owner.full_name", read_only=True)
    member_count = serializers.IntegerField(read_only=True)
    branch_count = serializers.IntegerField(read_only=True)
    plan_code = serializers.SerializerMethodField()
    subscription_status = serializers.SerializerMethodField()

    class Meta:
        model = Business
        fields = [
            "id", "name", "slug", "business_type", "status", "phone", "email",
            "city", "region", "country", "currency", "logo",
            "owner_email", "owner_name",
            "member_count", "branch_count",
            "plan_code", "subscription_status",
            "created_at", "updated_at",
        ]

    def get_plan_code(self, obj):
        sub = getattr(obj, "subscription", None)
        return sub.plan.code if sub and sub.plan_id else None

    def get_subscription_status(self, obj):
        sub = getattr(obj, "subscription", None)
        return sub.status if sub else None


class AdminBusinessDetailSerializer(AdminBusinessSerializer):
    members = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()

    class Meta(AdminBusinessSerializer.Meta):
        fields = AdminBusinessSerializer.Meta.fields + ["members", "stats"]

    def get_members(self, obj):
        ms = obj.memberships.select_related("user", "role")[:50]
        return [
            {
                "id": str(m.id),
                "user": m.user.full_name or m.user.email,
                "email": m.user.email,
                "role": m.role.code,
                "status": m.status,
            }
            for m in ms
        ]

    def get_stats(self, obj):
        from apps.customers.models import Customer
        from apps.products.models import Product
        from apps.sales.models import Sale
        from apps.suppliers.models import Supplier

        return {
            "customers": Customer.objects.filter(business=obj).count(),
            "products": Product.objects.filter(business=obj).count(),
            "suppliers": Supplier.objects.filter(business=obj).count(),
            "sales": Sale.objects.filter(business=obj).count(),
        }


class AdminAuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="user.email", read_only=True)
    actor_name = serializers.CharField(source="user.full_name", read_only=True)
    business_name = serializers.CharField(source="business.name", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id", "action", "resource_type", "resource_id",
            "actor_email", "actor_name", "business_name",
            "old_values", "new_values", "ip_address", "user_agent",
            "request_id", "created_at",
        ]


class AdminNotificationSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    business_name = serializers.CharField(source="business.name", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id", "user_email", "business_name", "type", "title",
            "message", "read_at", "created_at",
        ]
