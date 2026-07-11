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
    DailyTokenQuotaDecision,
)


DAILY_TOKEN_QUOTA_EXCEEDED = (
    "daily_token_quota_exceeded"
)


@dataclass(
    frozen=True,
    slots=True,
)
class DailyTokenQuotaError(
    Exception
):
    code: str
    message: str
    decision: DailyTokenQuotaDecision


def is_openai_compatible_path(
    path: str,
) -> bool:
    return path.startswith("/v1/")


def token_quota_headers(
    decision: DailyTokenQuotaDecision,
    *,
    include_retry_after: bool,
) -> dict[str, str]:
    headers = {
        "X-TokenQuota-Limit": str(
            decision.limit
        ),
        "X-TokenQuota-Used": str(
            decision.used_tokens
        ),
        "X-TokenQuota-Remaining": str(
            decision.remaining_tokens
        ),
        "X-TokenQuota-Reset": str(
            int(
                decision
                .reset_at
                .timestamp()
            )
        ),
    }

    if include_retry_after:
        headers["Retry-After"] = str(
            max(
                1,
                decision
                .retry_after_seconds,
            )
        )

    return headers


async def daily_token_quota_handler(
    request: Request,
    exc: DailyTokenQuotaError,
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
        headers=token_quota_headers(
            exc.decision,
            include_retry_after=True,
        ),
    )


def install_daily_token_quota_handler(
    app: FastAPI,
) -> None:
    app.add_exception_handler(
        DailyTokenQuotaError,
        daily_token_quota_handler,
    )


def install_token_quota_headers_middleware(
    app: FastAPI,
) -> None:
    @app.middleware("http")
    async def add_token_quota_headers(
        request: Request,
        call_next,
    ):
        response = await call_next(request)

        decision = getattr(
            request.state,
            "daily_token_quota_decision",
            None,
        )

        if decision is not None:
            for key, value in (
                token_quota_headers(
                    decision,
                    include_retry_after=False,
                ).items()
            ):
                response.headers.setdefault(
                    key,
                    value,
                )

        return response
