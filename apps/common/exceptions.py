"""Centralized error codes + exception handling.

Every API error is returned in the shape:
{
    "success": false,
    "error": {"code": "...", "message": "...", "details": {...}},
    "request_id": "..."
}
"""

import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("fomo.errors")


class ErrorCode:
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    BUSINESS_REQUIRED = "BUSINESS_REQUIRED"
    BUSINESS_NOT_FOUND = "BUSINESS_NOT_FOUND"
    BUSINESS_INACTIVE = "BUSINESS_INACTIVE"
    MEMBERSHIP_REQUIRED = "MEMBERSHIP_REQUIRED"
    PRODUCT_NOT_FOUND = "PRODUCT_NOT_FOUND"
    INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
    NEGATIVE_STOCK_NOT_ALLOWED = "NEGATIVE_STOCK_NOT_ALLOWED"
    DUPLICATE_SKU = "DUPLICATE_SKU"
    DUPLICATE_BARCODE = "DUPLICATE_BARCODE"
    SALE_ALREADY_COMPLETED = "SALE_ALREADY_COMPLETED"
    SALE_ALREADY_CANCELLED = "SALE_ALREADY_CANCELLED"
    SALE_NOT_COMPLETABLE = "SALE_NOT_COMPLETABLE"
    INVOICE_ALREADY_PAID = "INVOICE_ALREADY_PAID"
    INVOICE_CANCELLED = "INVOICE_CANCELLED"
    INVALID_PAYMENT_AMOUNT = "INVALID_PAYMENT_AMOUNT"
    PLAN_LIMIT_REACHED = "PLAN_LIMIT_REACHED"
    FEATURE_NOT_AVAILABLE = "FEATURE_NOT_AVAILABLE"
    FEATURE_NOT_INCLUDED = "FEATURE_NOT_INCLUDED"
    REPORT_NOT_FOUND = "REPORT_NOT_FOUND"
    SUBSCRIPTION_INACTIVE = "SUBSCRIPTION_INACTIVE"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class APIError(drf_exceptions.APIException):
    """Base class for domain errors raised from services."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "An error occurred."
    default_code = ErrorCode.VALIDATION_ERROR

    def __init__(self, detail=None, code=None, status_code=None, details=None):
        if status_code is not None:
            self.status_code = status_code
        self.error_code = code or self.default_code
        self.extra_details = details or {}
        super().__init__(detail=detail or self.default_detail, code=code)


class BusinessRequiredError(APIError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "An active business context is required (X-Business-ID header)."
    default_code = ErrorCode.BUSINESS_REQUIRED


class TenantViolationError(APIError):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have access to this business."
    default_code = ErrorCode.PERMISSION_DENIED


class InsufficientStockError(APIError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Insufficient stock for this operation."
    default_code = ErrorCode.INSUFFICIENT_STOCK


class PlanLimitReachedError(APIError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = "Your subscription plan limit has been reached."
    default_code = ErrorCode.PLAN_LIMIT_REACHED


class FeatureNotAvailableError(APIError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = "This feature is not available on your plan."
    default_code = ErrorCode.FEATURE_NOT_AVAILABLE


class BusinessRuleViolation(APIError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Business rule violation."
    default_code = ErrorCode.INVALID_STATE_TRANSITION


def _envelope(request, code, message, details, http_status):
    request_id = getattr(request, "id", None)
    body = {
        "success": False,
        "error": {"code": code, "message": message, "details": details},
        "request_id": request_id,
    }
    return Response(body, status=http_status)


def fomo_exception_handler(exc, context):
    request = context.get("request")

    if isinstance(exc, APIError):
        return _envelope(
            request,
            exc.error_code,
            str(exc.detail),
            exc.extra_details,
            exc.status_code,
        )

    if isinstance(exc, drf_exceptions.ValidationError):
        return _envelope(
            request,
            ErrorCode.VALIDATION_ERROR,
            "Invalid request.",
            exc.detail,
            status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, drf_exceptions.AuthenticationFailed):
        code = ErrorCode.AUTH_INVALID_CREDENTIALS
        message = str(exc.detail)
        if getattr(exc, "code", None) == "token_not_valid":
            code = ErrorCode.AUTH_TOKEN_EXPIRED
            message = "Token is invalid or expired."
        return _envelope(request, code, message, {}, exc.status_code)

    if isinstance(exc, drf_exceptions.NotAuthenticated):
        return _envelope(
            request,
            ErrorCode.AUTH_REQUIRED,
            "Authentication credentials were not provided.",
            {},
            status.HTTP_401_UNAUTHORIZED,
        )

    if isinstance(exc, (drf_exceptions.PermissionDenied, DjangoPermissionDenied)):
        return _envelope(
            request,
            ErrorCode.PERMISSION_DENIED,
            "You do not have permission to perform this action.",
            {},
            status.HTTP_403_FORBIDDEN,
        )

    if isinstance(exc, (drf_exceptions.NotFound, Http404)):
        return _envelope(
            request,
            ErrorCode.NOT_FOUND,
            "Resource not found.",
            {},
            status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, drf_exceptions.Throttled):
        return _envelope(
            request,
            ErrorCode.RATE_LIMITED,
            "Too many requests. Please slow down.",
            {"wait_seconds": exc.wait},
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    response = drf_exception_handler(exc, context)
    if response is not None:
        return _envelope(
            request,
            "ERROR",
            getattr(exc, "detail", str(exc)),
            {},
            response.status_code,
        )

    # Unexpected — log internally, never expose details to the client
    logger.exception("Unhandled exception", exc_info=exc)
    return _envelope(
        request,
        ErrorCode.INTERNAL_ERROR,
        "An unexpected error occurred.",
        {},
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
