from __future__ import annotations

from dataclasses import dataclass

from fastapi import (
    FastAPI,
    Request,
)
from fastapi.responses import (
    JSONResponse,
)

from .models import (
    RateLimitDecision,
    RequestRateLimitResult,
)


USER_RATE_LIMIT_EXCEEDED = (
    "user_rate_limit_exceeded"
)
IP_RATE_LIMIT_EXCEEDED = (
    "ip_rate_limit_exceeded"
)


@dataclass(
    frozen=True,
    slots=True,
)
class RequestRateLimitError(
    Exception
):
    code: str
    message: str
    decision: RateLimitDecision


def is_openai_compatible_path(
    path: str,
) -> bool:
    return path.startswith("/v1/")


def _scope_header_name(
    scope: str,
) -> str:
    if scope == "ip":
        return "IP"

    return scope.title()


def decision_headers(
    decision: RateLimitDecision,
    *,
    include_generic: bool,
) -> dict[str, str]:
    reset = str(
        int(decision.reset_at.timestamp())
    )
    scope_name = _scope_header_name(
        decision.scope
    )

    headers = {
        (
            f"X-RateLimit-"
            f"{scope_name}-Limit"
        ): str(decision.limit),
        (
            f"X-RateLimit-"
            f"{scope_name}-Remaining"
        ): str(decision.remaining),
        (
            f"X-RateLimit-"
            f"{scope_name}-Reset"
        ): reset,
    }

    if include_generic:
        headers.update({
            "Retry-After": str(
                max(
                    1,
                    decision.retry_after_seconds,
                )
            ),
            "X-RateLimit-Scope": (
                decision.scope
            ),
            "X-RateLimit-Limit": str(
                decision.limit
            ),
            "X-RateLimit-Remaining": str(
                decision.remaining
            ),
            "X-RateLimit-Reset": reset,
        })

    return headers


def result_headers(
    result: RequestRateLimitResult,
) -> dict[str, str]:
    headers = {}

    for decision in result.decisions:
        headers.update(
            decision_headers(
                decision,
                include_generic=False,
            )
        )

    return headers


async def request_rate_limit_handler(
    request: Request,
    exc: RequestRateLimitError,
) -> JSONResponse:
    if is_openai_compatible_path(
        request.url.path
    ):
        content = {
            "error": {
                "message": exc.message,
                "type": "rate_limit_error",
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

    return JSONResponse(
        status_code=429,
        content=content,
        headers=decision_headers(
            exc.decision,
            include_generic=True,
        ),
    )


def install_request_rate_limit_handler(
    app: FastAPI,
) -> None:
    app.add_exception_handler(
        RequestRateLimitError,
        request_rate_limit_handler,
    )


def install_rate_limit_headers_middleware(
    app: FastAPI,
) -> None:
    @app.middleware("http")
    async def add_rate_limit_headers(
        request: Request,
        call_next,
    ):
        response = await call_next(request)

        result = getattr(
            request.state,
            "request_rate_limit_result",
            None,
        )

        if result is not None:
            for key, value in (
                result_headers(result).items()
            ):
                response.headers.setdefault(
                    key,
                    value,
                )

        return response
