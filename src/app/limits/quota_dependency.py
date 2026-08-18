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
from src.app.db.session import (
    get_session_factory,
)

from .models import (
    DailyTokenQuotaDecision,
)
from .quota import (
    DailyTokenQuotaService,
)
from .quota_http import (
    DAILY_TOKEN_QUOTA_EXCEEDED,
    DailyTokenQuotaError,
)


def enforce_daily_token_quota(
    request: Request,
    caller: CallerIdentity | None = Depends(
        require_api_key
    ),
) -> DailyTokenQuotaDecision | None:
    if not settings.TOKEN_QUOTA_ENABLED:
        request.state.daily_token_quota_decision = (
            None
        )
        return None

    # API_AUTH_ENABLED=false 的迁移兼容模式下，
    # 没有稳定 caller，不执行用户 token quota。
    if caller is None:
        request.state.daily_token_quota_decision = (
            None
        )
        return None

    with (
        get_session_factory()()
        as session
    ):
        decision = DailyTokenQuotaService(
            session,
            limit=(
                settings
                .DAILY_TOKEN_QUOTA_TOKENS
            ),
        ).check(
            caller.key_id
        )

    request.state.daily_token_quota_decision = (
        decision
    )

    if decision.allowed:
        return decision

    raise DailyTokenQuotaError(
        code=DAILY_TOKEN_QUOTA_EXCEEDED,
        message=(
            "Daily token quota exceeded"
        ),
        decision=decision,
    )
