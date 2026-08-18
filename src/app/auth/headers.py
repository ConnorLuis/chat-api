from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import Request

from .http import (
    API_KEY_INVALID,
    API_KEY_MISSING,
    APIKeyAuthenticationError,
)


@dataclass(
    frozen=True,
    slots=True,
)
class APIKeyCredential:
    plaintext: str
    authentication_method: str


def extract_api_key_credential(
    request: Request,
) -> APIKeyCredential:
    authorization_present = (
        "authorization"
        in request.headers
    )
    x_api_key_present = (
        "x-api-key"
        in request.headers
    )

    bearer_key: str | None = None
    x_api_key: str | None = None

    if authorization_present:
        authorization = (
            request.headers.get(
                "authorization",
                "",
            )
        )

        parts = authorization.strip().split(
            None,
            1,
        )

        if (
            len(parts) != 2
            or parts[0].lower()
            != "bearer"
            or not parts[1].strip()
        ):
            raise APIKeyAuthenticationError(
                code=API_KEY_INVALID,
                message="Invalid API key",
            )

        bearer_key = parts[1].strip()

    if x_api_key_present:
        x_api_key = request.headers.get(
            "x-api-key",
            "",
        ).strip()

        if not x_api_key:
            raise APIKeyAuthenticationError(
                code=API_KEY_INVALID,
                message="Invalid API key",
            )

    if (
        bearer_key is None
        and x_api_key is None
    ):
        raise APIKeyAuthenticationError(
            code=API_KEY_MISSING,
            message="API key is required",
        )

    if (
        bearer_key is not None
        and x_api_key is not None
        and not hmac.compare_digest(
            bearer_key,
            x_api_key,
        )
    ):
        raise APIKeyAuthenticationError(
            code=API_KEY_INVALID,
            message=(
                "Authorization and "
                "X-API-Key credentials "
                "do not match"
            ),
        )

    if bearer_key is not None:
        return APIKeyCredential(
            plaintext=bearer_key,
            authentication_method="bearer",
        )

    assert x_api_key is not None

    return APIKeyCredential(
        plaintext=x_api_key,
        authentication_method="x-api-key",
    )
