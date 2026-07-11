from __future__ import annotations

from fastapi import (
    Depends,
    Request,
)

from src.app.auth.dependency import (
    require_api_key,
)
from src.app.auth.identity import (
    CallerIdentity,
)
from src.app.core.settings import (
    settings,
)

from .client_ip import get_client_ip
from .http import (
    IP_RATE_LIMIT_EXCEEDED,
    USER_RATE_LIMIT_EXCEEDED,
    RequestRateLimitError,
)
from .models import (
    RateLimitPolicy,
    RequestRateLimitResult,
)
from .service import (
    IP_RATE_LIMIT_SCOPE,
    USER_RATE_LIMIT_SCOPE,
    RequestRateLimitService,
)
from .store import (
    InMemorySlidingWindowStore,
)


_default_request_rate_limit_store = (
    InMemorySlidingWindowStore()
)


def get_request_rate_limit_service(
) -> RequestRateLimitService:
    return RequestRateLimitService(
        user_policy=RateLimitPolicy(
            scope=USER_RATE_LIMIT_SCOPE,
            limit=(
                settings
                .USER_RATE_LIMIT_REQUESTS
            ),
            window_seconds=(
                settings
                .USER_RATE_LIMIT_WINDOW_SECONDS
            ),
        ),
        ip_policy=RateLimitPolicy(
            scope=IP_RATE_LIMIT_SCOPE,
            limit=(
                settings
                .IP_RATE_LIMIT_REQUESTS
            ),
            window_seconds=(
                settings
                .IP_RATE_LIMIT_WINDOW_SECONDS
            ),
        ),
        store=(
            _default_request_rate_limit_store
        ),
    )


def reset_request_rate_limit_store(
) -> None:
    _default_request_rate_limit_store.clear_all()


def enforce_request_limits(
    request: Request,
    caller: CallerIdentity | None = Depends(
        require_api_key
    ),
    service: RequestRateLimitService = Depends(
        get_request_rate_limit_service
    ),
) -> RequestRateLimitResult | None:
    if not settings.REQUEST_RATE_LIMIT_ENABLED:
        request.state.request_rate_limit_result = (
            None
        )
        return None

    client_ip = get_client_ip(
        request,
        trust_proxy_headers=(
            settings
            .RATE_LIMIT_TRUST_PROXY_HEADERS
        ),
    )

    result = service.check_request(
        caller=caller,
        client_ip=client_ip,
    )

    request.state.request_rate_limit_result = (
        result
    )

    exceeded = result.exceeded

    if exceeded is None:
        return result

    if exceeded.scope == USER_RATE_LIMIT_SCOPE:
        raise RequestRateLimitError(
            code=USER_RATE_LIMIT_EXCEEDED,
            message=(
                "User request rate limit "
                "exceeded"
            ),
            decision=exceeded,
        )

    raise RequestRateLimitError(
        code=IP_RATE_LIMIT_EXCEEDED,
        message=(
            "IP request rate limit exceeded"
        ),
        decision=exceeded,
    )
