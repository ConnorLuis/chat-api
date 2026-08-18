from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    Request,
)

from src.app.auth.dependency import (
    get_caller_identity,
    require_api_key,
)
from src.app.core.settings import (
    settings,
)

from .schemas import (
    CallerIdentityResponse,
)


router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
    dependencies=[
        Depends(require_api_key),
    ],
)


@router.get(
    "/whoami",
    response_model=(
        CallerIdentityResponse
    ),
)
def whoami(
    request: Request,
):
    caller = get_caller_identity(
        request
    )

    if caller is None:
        return {
            "authenticated": False,
            "auth_enabled": (
                settings.API_AUTH_ENABLED
            ),
        }

    return {
        "authenticated": True,
        "auth_enabled": True,
        "key_id": caller.key_id,
        "key_prefix": (
            caller.key_prefix
        ),
        "key_name": caller.key_name,
        "authentication_method": (
            caller.authentication_method
        ),
        "authenticated_at": (
            caller.authenticated_at
        ),
    }
