"""Error envelope and exception handlers.

Every error response has the shape documented in API_DOCUMENTATION.md:

    {"error": {"code": "<stable_code>", "message": "<human readable>", "details": {...}}}

Domain code raises :class:`AppError` (or a subclass); FastAPI validation errors become
``validation_error`` with ``details.fields``; anything unexpected becomes ``internal_error``
without leaking internals.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

log = get_logger(__name__)


class AppError(Exception):
    """Base class for domain errors that map 1:1 to an HTTP error envelope."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"
    message: str = "Bad request."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details: dict[str, Any] = dict(details or {})
        self.headers: dict[str, str] = dict(headers or {})
        super().__init__(self.message)


class Unauthenticated(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthenticated"
    message = "Authentication required."


class Forbidden(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    message = "You are not allowed to do that."


class NotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "Not found."


class Conflict(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "Conflict."


class Gone(AppError):
    status_code = status.HTTP_410_GONE
    code = "gone"
    message = "This resource is no longer available."


class PayloadTooLarge(AppError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    code = "file_too_large"
    message = "The uploaded file is too large."


class UnprocessableEntity(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "unprocessable"
    message = "The request could not be processed."


class RateLimited(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    message = "Too many requests."

    def __init__(self, retry_after: int, **kwargs: Any) -> None:
        headers = {"Retry-After": str(max(1, retry_after))}
        super().__init__(details={"retry_after": max(1, retry_after)}, headers=headers, **kwargs)


class ServiceUnavailable(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_unavailable"
    message = "Service temporarily unavailable."


class InternalError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "internal_error"
    message = "Something went wrong on our side."


_HTTP_STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    406: "not_acceptable",
    408: "request_timeout",
    409: "conflict",
    410: "gone",
    411: "length_required",
    413: "file_too_large",
    415: "unsupported_media_type",
    416: "range_not_satisfiable",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    501: "not_implemented",
    503: "service_unavailable",
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": dict(details or {})}},
        headers=dict(headers or {}),
    )


def _validation_fields(exc: RequestValidationError) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", ())]
        fields.append(
            {"loc": loc, "msg": str(err.get("msg", "")), "type": str(err.get("type", ""))}
        )
    return fields


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, exc.details, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "validation_error",
            "The request is invalid.",
            {"fields": _validation_fields(exc)},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        code = _HTTP_STATUS_CODES.get(exc.status_code, "error")
        message: str
        details: dict[str, Any] = {}
        if isinstance(detail, dict) and "code" in detail:
            code = str(detail.get("code", code))
            message = str(detail.get("message", ""))
            details = dict(detail.get("details") or {})
        else:
            message = str(detail) if detail else code.replace("_", " ").capitalize() + "."
        headers = dict(exc.headers or {}) if isinstance(exc, HTTPException) else {}
        return error_response(exc.status_code, code, message, details, headers)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_exception", exc_type=type(exc).__name__)
        return error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "Something went wrong on our side.",
        )
