"""Centralized error model.

All application failures are raised as typed domain exceptions. A single
exception handler converts them into consistent, user-safe API responses.
Technical details are logged internally and never leaked to clients.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for all domain errors."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "app_error"
    message: str = "Something went wrong. Please try again."
    retryable: bool = False

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        code: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Any] = None,
        retryable: bool | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        if status_code is not None:
            self.status_code = status_code
        if retryable is not None:
            self.retryable = retryable
        self.details = details
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "The requested resource could not be found."


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"
    message = "You must be signed in to do that."
    retryable = True


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    message = "You do not have permission to do that."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "The request conflicts with the current state."


class ValidationAppError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"
    message = "Please check the information you entered."


class TooManyRequestsError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    message = "Too many requests. Please slow down and try again."
    retryable = True


class ServiceUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_unavailable"
    message = "EnvyChat is temporarily unavailable. Please try again."
    retryable = True


def _error_payload(exc: AppError) -> dict:
    return {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "retryable": exc.retryable,
            "details": exc.details,
        }
    }


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "app error handled",
            extra={
                "path": request.url.path,
                "code": exc.code,
                "status": exc.status_code,
            },
        )
        return JSONResponse(
            status_code=exc.status_code, content=_error_payload(exc)
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(loc) for loc in err.get("loc", [])),
                "message": err.get("msg", "invalid value"),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Please check the information you entered.",
                    "retryable": False,
                    "details": errors[:10],
                }
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log full technical details internally (never exposed to users).
        logger.exception(
            "unhandled error",
            extra={"path": request.url.path, "error": repr(exc)},
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_payload(
                AppError(
                    status_code=500,
                    code="internal_error",
                    message="Something went wrong. Please try again.",
                    retryable=True,
                )
            ),
        )