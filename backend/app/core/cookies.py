"""Cookie names and helpers shared by the auth router and the dependencies."""

from __future__ import annotations

from fastapi import Response

from app.core.config import Settings

ACCESS_COOKIE = "pv_access"
REFRESH_COOKIE = "pv_refresh"
CSRF_COOKIE = "pv_csrf"
CSRF_HEADER = "X-CSRF-Token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
    settings: Settings,
) -> None:
    secure = settings.cookie_secure
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=settings.ACCESS_TOKEN_TTL_SECONDS,
        path="/",
        domain=settings.COOKIE_DOMAIN,
        secure=secure,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=settings.REFRESH_TOKEN_TTL_SECONDS,
        path=REFRESH_COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
        secure=secure,
        httponly=True,
        samesite="lax",
    )
    set_csrf_cookie(response, csrf_token, settings=settings)


def set_csrf_cookie(response: Response, csrf_token: str, *, settings: Settings) -> None:
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=settings.CSRF_COOKIE_TTL_SECONDS,
        path="/",
        domain=settings.COOKIE_DOMAIN,
        secure=settings.cookie_secure,
        httponly=False,  # must be readable by the frontend to echo in X-CSRF-Token
        samesite="lax",
    )


def clear_auth_cookies(response: Response, *, settings: Settings) -> None:
    for name, path in (
        (ACCESS_COOKIE, "/"),
        (REFRESH_COOKIE, REFRESH_COOKIE_PATH),
        (CSRF_COOKIE, "/"),
    ):
        response.set_cookie(
            name,
            "",
            max_age=0,
            expires=0,
            path=path,
            domain=settings.COOKIE_DOMAIN,
            secure=settings.cookie_secure,
            httponly=name != CSRF_COOKIE,
            samesite="lax",
        )
