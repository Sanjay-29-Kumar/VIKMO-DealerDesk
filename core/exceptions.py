from django.http import Http404
from django.core.exceptions import PermissionDenied
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    NotFound as DRFNotFound,
    ValidationError as DRFValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler


class DealerDeskAPIException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "VALIDATION_ERROR"
    message = "An error occurred."
    details = []

    def __init__(self, message=None, code=None, details=None, status_code=None):
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        if message is not None:
            self.message = message
        if details is not None:
            self.details = details if isinstance(details, list) else [details]
        else:
            self.details = []
        super().__init__(self.message)


class NotFoundException(DealerDeskAPIException):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"

    def __init__(self, message="Resource not found.", details=None):
        super().__init__(message=message, code=self.code, details=details, status_code=self.status_code)


class InsufficientStockException(DealerDeskAPIException):
    status_code = status.HTTP_409_CONFLICT
    code = "INSUFFICIENT_STOCK"

    def __init__(self, message, details=None):
        super().__init__(message=message, code=self.code, details=details, status_code=self.status_code)


class InvalidTransitionException(DealerDeskAPIException):
    status_code = status.HTTP_409_CONFLICT
    code = "INVALID_TRANSITION"

    def __init__(self, message="Invalid order status transition.", details=None):
        super().__init__(message=message, code=self.code, details=details, status_code=self.status_code)


class OrderLockedException(DealerDeskAPIException):
    status_code = status.HTTP_409_CONFLICT
    code = "ORDER_LOCKED"

    def __init__(self, message="Order cannot be edited in its current status.", details=None):
        super().__init__(message=message, code=self.code, details=details, status_code=self.status_code)


class IdempotencyConflictException(DealerDeskAPIException):
    status_code = status.HTTP_409_CONFLICT
    code = "IDEMPOTENCY_CONFLICT"

    def __init__(self, message="Idempotency-Key reused with different request payload.", details=None):
        super().__init__(message=message, code=self.code, details=details, status_code=self.status_code)


class DuplicateException(DealerDeskAPIException):
    status_code = status.HTTP_409_CONFLICT
    code = "DUPLICATE"

    def __init__(self, message, details=None):
        super().__init__(message=message, code=self.code, details=details, status_code=self.status_code)


class SupplierUnavailableException(DealerDeskAPIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "SUPPLIER_UNAVAILABLE"

    def __init__(self, message="Supplier API unavailable after max retries.", details=None):
        super().__init__(message=message, code=self.code, details=details, status_code=self.status_code)


def custom_exception_handler(exc, context):
    """
    Standard exception handler conforming strictly to API_CONTRACT.md section 3:
    {"error": {"code": "CODE", "message": "Human readable text", "details": []}}
    """
    if isinstance(exc, DealerDeskAPIException):
        return Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details if isinstance(exc.details, list) else [],
                }
            },
            status=exc.status_code,
        )

    if isinstance(exc, (Http404, DRFNotFound)):
        return Response(
            {
                "error": {
                    "code": "NOT_FOUND",
                    "message": str(exc) if str(exc) else "Resource not found.",
                    "details": [],
                }
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, DRFValidationError):
        details = []
        message_parts = []
        if isinstance(exc.detail, dict):
            for field, errs in exc.detail.items():
                if isinstance(errs, list):
                    for e in errs:
                        details.append({"field": field, "error": str(e)})
                        message_parts.append(f"{field}: {e}")
                else:
                    details.append({"field": field, "error": str(errs)})
                    message_parts.append(f"{field}: {errs}")
        elif isinstance(exc.detail, list):
            for e in exc.detail:
                details.append({"error": str(e)})
                message_parts.append(str(e))
        else:
            details.append({"error": str(exc.detail)})
            message_parts.append(str(exc.detail))

        msg = "; ".join(message_parts) if message_parts else "Validation error occurred."
        return Response(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": msg,
                    "details": details,
                }
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = exception_handler(exc, context)
    if response is not None:
        return Response(
            {
                "error": {
                    "code": "VALIDATION_ERROR" if response.status_code == 400 else "ERROR",
                    "message": str(exc),
                    "details": [],
                }
            },
            status=response.status_code,
        )

    return Response(
        {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected internal error occurred.",
                "details": [str(exc)],
            }
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
