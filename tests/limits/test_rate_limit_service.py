from datetime import (
    datetime,
    timezone,
)

from src.app.auth.identity import (
    CallerIdentity,
)
from src.app.limits import (
    IP_RATE_LIMIT_SCOPE,
    USER_RATE_LIMIT_SCOPE,
    RateLimitPolicy,
    RequestRateLimitService,
)


NOW = datetime(
    2026,
    7,
    11,
    12,
    0,
    tzinfo=timezone.utc,
)


class FixedClock:
    def now(self) -> datetime:
        return NOW


def build_service():
    return RequestRateLimitService(
        user_policy=RateLimitPolicy(
            scope=USER_RATE_LIMIT_SCOPE,
            limit=1,
            window_seconds=60,
        ),
        ip_policy=RateLimitPolicy(
            scope=IP_RATE_LIMIT_SCOPE,
            limit=1,
            window_seconds=60,
        ),
        clock=FixedClock(),
    )


def build_caller(
    key_id: str,
) -> CallerIdentity:
    return CallerIdentity(
        key_id=key_id,
        key_prefix="chat_sk_test",
        key_name="test key",
        authenticated_at=NOW,
        authentication_method="bearer",
    )


def test_user_limit_is_skipped_without_caller():
    service = build_service()

    assert service.check_user(None) is None


def test_user_limit_uses_api_key_id():
    service = build_service()
    caller = build_caller("key-1")

    first = service.check_user(caller)
    second = service.check_user(caller)

    assert first is not None
    assert first.subject == "key-1"
    assert first.allowed is True

    assert second is not None
    assert second.allowed is False


def test_user_and_ip_limits_are_independent():
    service = build_service()
    caller = build_caller("key-1")

    user = service.check_user(caller)
    ip = service.check_ip(
        "203.0.113.10"
    )

    assert user is not None
    assert user.allowed is True
    assert ip.allowed is True
