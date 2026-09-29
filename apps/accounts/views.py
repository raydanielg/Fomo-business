from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.audit.models import AuditLog
from apps.audit.services import log as audit_log
from apps.common.exceptions import APIError, ErrorCode

from .models import AuthToken, DeviceSession, User
from .serializers import (
    ChangePasswordSerializer,
    DeletionRequestSerializer,
    DeviceSessionSerializer,
    EmailVerifySerializer,
    EmptySerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    UserSerializer,
)
from . import services


class AuthThrottle(AnonRateThrottle):
    scope = "auth"


def _client_meta(request):
    ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR")
    return ip, request.META.get("HTTP_USER_AGENT", "")


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = RegisterSerializer
    throttle_classes = [AuthThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        token = services.create_auth_token(user, AuthToken.Purpose.EMAIL_VERIFY)
        from apps.notifications.tasks import send_verification_email

        send_verification_email.delay(user_id=str(user.id), token=token.token)

        return Response(
            {
                "success": True,
                "data": UserSerializer(user).data,
                "message": "Registration successful. Please verify your email.",
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = LoginSerializer
    throttle_classes = [AuthThrottle]

    @extend_schema(request=LoginSerializer, responses={200: UserSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            audit_log(AuditLog.Action.LOGIN_FAILED, user=None)
            raise
        user = serializer.validated_data["user"]

        ip, ua = _client_meta(request)
        tokens = services.issue_tokens(
            user,
            device_name=serializer.validated_data.get("device_name", ""),
            ip_address=ip,
            user_agent=ua,
        )
        audit_log(AuditLog.Action.LOGIN, user=user, resource_type="User", resource_id=user.id)

        return Response(
            {
                "success": True,
                "data": {**tokens, "user": UserSerializer(user).data},
            }
        )


class RefreshView(TokenRefreshView):
    """Refresh with rotation + device-session revocation check."""

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                jti = token.get("jti")
                if jti and DeviceSession.objects.filter(
                    refresh_jti=jti, revoked_at__isnull=False
                ).exists():
                    raise APIError(
                        "This session has been revoked.",
                        code=ErrorCode.AUTH_TOKEN_EXPIRED,
                        status_code=status.HTTP_401_UNAUTHORIZED,
                    )
            except TokenError:
                pass  # let simplejwt produce the standard error
        response = super().post(request, *args, **kwargs)
        return response


class LogoutView(APIView):
    serializer_class = EmptySerializer

    @extend_schema(request=EmptySerializer)
    def post(self, request):
        refresh_token = request.data.get("refresh")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
                jti = token.get("jti")
                if jti:
                    services.revoke_session(request.user, jti)
            except TokenError:
                pass
        audit_log(AuditLog.Action.LOGOUT, user=request.user, resource_type="User", resource_id=request.user.id)
        return Response({"success": True, "message": "Logged out."})


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return ProfileUpdateSerializer
        return UserSerializer


class ChangePasswordView(APIView):
    serializer_class = ChangePasswordSerializer

    @extend_schema(request=ChangePasswordSerializer)
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        services.change_password(request.user, serializer.validated_data["new_password"])
        return Response(
            {"success": True, "message": "Password changed. All sessions revoked."}
        )


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = PasswordResetRequestSerializer
    throttle_classes = [AuthThrottle]

    @extend_schema(request=PasswordResetRequestSerializer)
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=serializer.validated_data["email"]).first()
        if user:
            token = services.create_auth_token(user, AuthToken.Purpose.PASSWORD_RESET)
            from apps.notifications.tasks import send_password_reset_email

            send_password_reset_email.delay(user_id=str(user.id), token=token.token)
        return Response(
            {
                "success": True,
                "found": bool(user),
                "message": (
                    "Reset link sent."
                    if user
                    else "If an account exists, a reset link has been sent."
                ),
            }
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = PasswordResetConfirmSerializer
    throttle_classes = [AuthThrottle]

    @extend_schema(request=PasswordResetConfirmSerializer)
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ok = services.reset_password(
            serializer.validated_data["token"],
            serializer.validated_data["new_password"],
        )
        if not ok:
            raise APIError(
                "Reset token is invalid or expired.",
                code=ErrorCode.VALIDATION_ERROR,
            )
        return Response({"success": True, "message": "Password has been reset."})


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = EmailVerifySerializer

    @extend_schema(request=EmailVerifySerializer)
    def post(self, request):
        serializer = EmailVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not services.verify_email(serializer.validated_data["token"]):
            raise APIError(
                "Verification token is invalid or expired.",
                code=ErrorCode.VALIDATION_ERROR,
            )
        return Response({"success": True, "message": "Email verified."})


class ResendVerificationView(APIView):
    serializer_class = EmptySerializer
    throttle_classes = [AuthThrottle]

    @extend_schema(request=EmptySerializer)
    def post(self, request):
        user = request.user
        if user.is_verified:
            return Response({"success": True, "message": "Email already verified."})
        token = services.create_auth_token(user, AuthToken.Purpose.EMAIL_VERIFY)
        from apps.notifications.tasks import send_verification_email

        send_verification_email.delay(user_id=str(user.id), token=token.token)
        return Response({"success": True, "message": "Verification email sent."})


class DeactivateAccountView(APIView):
    serializer_class = DeletionRequestSerializer

    @extend_schema(request=DeletionRequestSerializer)
    def post(self, request):
        serializer = DeletionRequestSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.is_active = False
        user.save(update_fields=["is_active"])
        user.sessions.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
        return Response({"success": True, "message": "Account deactivated."})


class RequestDeletionView(APIView):
    serializer_class = DeletionRequestSerializer

    @extend_schema(request=DeletionRequestSerializer)
    def post(self, request):
        serializer = DeletionRequestSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        services.request_account_deletion(request.user)
        return Response(
            {
                "success": True,
                "message": "Deletion request recorded. Your data will be handled per our retention policy.",
            }
        )


@extend_schema_view(list=extend_schema(description="List active device sessions"))
class DeviceSessionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DeviceSession.objects.none()
    serializer_class = DeviceSessionSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return DeviceSession.objects.none()
        return DeviceSession.objects.filter(
            user=self.request.user, revoked_at__isnull=True
        )

    def destroy(self, request, *args, **kwargs):
        session = self.get_object()
        session.revoked_at = timezone.now()
        session.save(update_fields=["revoked_at"])
        return Response({"success": True, "message": "Session revoked."})
