from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from src.app.limits import (
    InMemorySlidingWindowStore,
    RateLimitPolicy,
)


BASE_TIME = datetime(
    2026,
    7,
    11,
    12,
    0,
    tzinfo=timezone.utc,
)


def test_policy_rejects_invalid_values():
    invalid_values = [
        {
            "scope": "",
            "limit": 1,
            "window_seconds": 1,
        },
        {
            "scope": "user",
            "limit": 0,
            "window_seconds": 1,
        },
        {
            "scope": "user",
            "limit": 1,
            "window_seconds": 0,
        },
    ]

    for values in invalid_values:
        with pytest.raises(ValueError):
            RateLimitPolicy(**values)


def test_allows_up_to_limit():
    store = InMemorySlidingWindowStore()
    policy = RateLimitPolicy(
        scope="user",
        limit=2,
        window_seconds=60,
    )

    first = store.consume(
        policy=policy,
        subject="key-1",
        now=BASE_TIME,
    )
    second = store.consume(
        policy=policy,
        subject="key-1",
        now=BASE_TIME
        + timedelta(seconds=1),
    )

    assert first.allowed is True
    assert first.remaining == 1
    assert second.allowed is True
    assert second.remaining == 0


def test_denies_when_window_is_full():
    store = InMemorySlidingWindowStore()
    policy = RateLimitPolicy(
        scope="user",
        limit=1,
        window_seconds=60,
    )

    store.consume(
        policy=policy,
        subject="key-1",
        now=BASE_TIME,
    )

    denied = store.consume(
        policy=policy,
        subject="key-1",
        now=BASE_TIME
        + timedelta(seconds=10),
    )

    assert denied.allowed is False
    assert denied.remaining == 0
    assert denied.retry_after_seconds == 50
    assert denied.reset_at == (
        BASE_TIME
        + timedelta(seconds=60)
    )


def test_expired_events_leave_window():
    store = InMemorySlidingWindowStore()
    policy = RateLimitPolicy(
        scope="user",
        limit=1,
        window_seconds=60,
    )

    store.consume(
        policy=policy,
        subject="key-1",
        now=BASE_TIME,
    )

    allowed = store.consume(
        policy=policy,
        subject="key-1",
        now=BASE_TIME
        + timedelta(seconds=60),
    )

    assert allowed.allowed is True
    assert allowed.remaining == 0


def test_subjects_are_isolated():
    store = InMemorySlidingWindowStore()
    policy = RateLimitPolicy(
        scope="user",
        limit=1,
        window_seconds=60,
    )

    first = store.consume(
        policy=policy,
        subject="key-1",
        now=BASE_TIME,
    )
    second = store.consume(
        policy=policy,
        subject="key-2",
        now=BASE_TIME,
    )

    assert first.allowed is True
    assert second.allowed is True


def test_scopes_are_isolated():
    store = InMemorySlidingWindowStore()

    user_policy = RateLimitPolicy(
        scope="user",
        limit=1,
        window_seconds=60,
    )
    ip_policy = RateLimitPolicy(
        scope="ip",
        limit=1,
        window_seconds=60,
    )

    user = store.consume(
        policy=user_policy,
        subject="same-subject",
        now=BASE_TIME,
    )
    ip = store.consume(
        policy=ip_policy,
        subject="same-subject",
        now=BASE_TIME,
    )

    assert user.allowed is True
    assert ip.allowed is True


def test_clear_removes_one_subject():
    store = InMemorySlidingWindowStore()
    policy = RateLimitPolicy(
        scope="user",
        limit=1,
        window_seconds=60,
    )

    store.consume(
        policy=policy,
        subject="key-1",
        now=BASE_TIME,
    )

    store.clear(
        scope="user",
        subject="key-1",
    )

    allowed = store.consume(
        policy=policy,
        subject="key-1",
        now=BASE_TIME,
    )

    assert allowed.allowed is True


def test_consume_many_does_not_partially_consume():
    store = InMemorySlidingWindowStore()

    user_policy = RateLimitPolicy(
        scope="user",
        limit=1,
        window_seconds=60,
    )
    ip_policy = RateLimitPolicy(
        scope="ip",
        limit=2,
        window_seconds=60,
    )

    first = store.consume_many(
        entries=[
            (
                user_policy,
                "key-1",
            ),
            (
                ip_policy,
                "203.0.113.10",
            ),
        ],
        now=BASE_TIME,
    )

    assert all(
        decision.allowed
        for decision in first
    )

    denied = store.consume_many(
        entries=[
            (
                user_policy,
                "key-1",
            ),
            (
                ip_policy,
                "203.0.113.10",
            ),
        ],
        now=BASE_TIME,
    )

    assert denied[0].allowed is False
    assert denied[1].allowed is True
    assert denied[1].remaining == 1

    # 上一个整体被拒绝的请求没有消耗 IP 次数，
    # 因此新用户仍可通过同一个 IP 发起第二次请求。
    third = store.consume_many(
        entries=[
            (
                user_policy,
                "key-2",
            ),
            (
                ip_policy,
                "203.0.113.10",
            ),
        ],
        now=BASE_TIME,
    )

    assert all(
        decision.allowed
        for decision in third
    )
    assert third[1].remaining == 0
