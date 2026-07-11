from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


API_KEY_MISSING = "api_key_missing"
API_KEY_INVALID = "api_key_invalid"
API_KEY_REVOKED = "api_key_revoked"

API_KEY_AUTH_NOT_CONFIGURED = (
    "api_key_auth_not_configured"
)


@dataclass(
    frozen=True,
    slots=True,
)
class APIKeyAuthenticationError(
    Exception
):
    """HTTP authentication boundary error."""

    code: str
    message: str
    status_code: int = 401


def is_openai_compatible_path(
    path: str,
) -> bool:
    return path.startswith("/v1/")


async def api_key_exception_handler(
    request: Request,
    exc: APIKeyAuthenticationError,
) -> JSONResponse:
    if is_openai_compatible_path(
        request.url.path
    ):
        content = {
            "error": {
                "message": exc.message,
                "type": (
                    "authentication_error"
                    if exc.status_code == 401
                    else "server_error"
                ),
                "param": None,
                "code": exc.code,
            }
        }
    else:
        content = {
            "detail": {
                "code": exc.code,
                "message": exc.message,
            }
        }

    headers = {}

    if exc.status_code == 401:
        headers[
            "WWW-Authenticate"
        ] = "Bearer"

    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=headers,
    )


def install_api_key_exception_handlers(
    app: FastAPI,
) -> None:
    app.add_exception_handler(
        APIKeyAuthenticationError,
        api_key_exception_handler,
    )
