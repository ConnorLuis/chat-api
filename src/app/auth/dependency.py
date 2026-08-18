from __future__ import annotations

from fastapi import Request

from src.app.core.settings import (
    settings,
)
from src.app.db.session import (
    get_session_factory,
)
from src.app.services.api_key_service import (
    APIKeyService,
)

from .errors import (
    APIKeyConfigurationError,
    InvalidAPIKeyError,
    RevokedAPIKeyError,
)
from .headers import (
    extract_api_key_credential,
)
from .http import (
    API_KEY_AUTH_NOT_CONFIGURED,
    API_KEY_INVALID,
    API_KEY_REVOKED,
    APIKeyAuthenticationError,
)
from .identity import CallerIdentity


def require_api_key(
    request: Request,
) -> CallerIdentity | None:
    """Authenticate one request.

    API_AUTH_ENABLED=false 时作为迁移兼容模式，
    不访问数据库，也不要求配置 pepper。
    """

    if not settings.API_AUTH_ENABLED:
        request.state.caller = None
        return None

    credential = (
        extract_api_key_credential(
            request
        )
    )

    try:
        with (
            get_session_factory()()
            as session
        ):
            caller = APIKeyService(
                session
            ).authenticate(
                credential.plaintext,
                authentication_method=(
                    credential
                    .authentication_method
                ),
            )

    except RevokedAPIKeyError as exc:
        raise APIKeyAuthenticationError(
            code=API_KEY_REVOKED,
            message=(
                "API key has been revoked"
            ),
        ) from exc

    except InvalidAPIKeyError as exc:
        raise APIKeyAuthenticationError(
            code=API_KEY_INVALID,
            message="Invalid API key",
        ) from exc

    except APIKeyConfigurationError as exc:
        raise APIKeyAuthenticationError(
            code=(
                API_KEY_AUTH_NOT_CONFIGURED
            ),
            message=(
                "API key authentication "
                "is not configured"
            ),
            status_code=500,
        ) from exc

    request.state.caller = caller

    return caller


def get_caller_identity(
    request: Request,
) -> CallerIdentity | None:
    return getattr(
        request.state,
        "caller",
        None,
    )
