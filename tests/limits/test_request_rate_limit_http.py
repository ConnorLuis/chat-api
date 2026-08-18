from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

import pytest

from src.app.limits import (
    IP_RATE_LIMIT_SCOPE,
    USER_RATE_LIMIT_SCOPE,
    RateLimitPolicy,
    RequestRateLimitService,
)
from src.app.limits.dependency import (
    get_request_rate_limit_service,
)
from src.app.main import app


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


@pytest.fixture
def rate_limit_http_context(
    auth_context,
    monkeypatch,
):
    original_override = (
        app.dependency_overrides.get(
            get_request_rate_limit_service
        )
    )

    def configure(
        *,
        user_limit: int,
        ip_limit: int,
    ):
        monkeypatch.setenv(
            "REQUEST_RATE_LIMIT_ENABLED",
            "true",
        )
        monkeypatch.setenv(
            "RATE_LIMIT_TRUST_PROXY_HEADERS",
            "true",
        )

        service = RequestRateLimitService(
            user_policy=RateLimitPolicy(
                scope=USER_RATE_LIMIT_SCOPE,
                limit=user_limit,
                window_seconds=60,
            ),
            ip_policy=RateLimitPolicy(
                scope=IP_RATE_LIMIT_SCOPE,
                limit=ip_limit,
                window_seconds=60,
            ),
            clock=FixedClock(),
        )

        app.dependency_overrides[
            get_request_rate_limit_service
        ] = lambda: service

        return {
            **auth_context,
            "service": service,
        }

    try:
        yield configure

    finally:
        if original_override is None:
            app.dependency_overrides.pop(
                get_request_rate_limit_service,
                None,
            )
        else:
            app.dependency_overrides[
                get_request_rate_limit_service
            ] = original_override


def request_headers(
    context,
    *,
    ip: str,
    authenticated: bool = True,
):
    headers = {
        "X-Forwarded-For": ip,
    }

    if authenticated:
        headers["X-API-Key"] = (
            context["api_key"]
        )

    return headers


def test_disabled_limit_does_not_add_headers(
    auth_context,
    monkeypatch,
):
    monkeypatch.setenv(
        "REQUEST_RATE_LIMIT_ENABLED",
        "false",
    )

    for _ in range(3):
        response = auth_context[
            "client"
        ].get(
            "/auth/whoami",
            headers={
                "X-API-Key": (
                    auth_context["api_key"]
                )
            },
        )

        assert response.status_code == 200
        assert (
            "x-ratelimit-user-limit"
            not in response.headers
        )


def test_allowed_request_has_user_and_ip_headers(
    rate_limit_http_context,
):
    context = rate_limit_http_context(
        user_limit=2,
        ip_limit=3,
    )

    response = context["client"].get(
        "/auth/whoami",
        headers=request_headers(
            context,
            ip="203.0.113.10",
        ),
    )

    assert response.status_code == 200

    assert response.headers[
        "x-ratelimit-user-limit"
    ] == "2"
    assert response.headers[
        "x-ratelimit-user-remaining"
    ] == "1"

    assert response.headers[
        "x-ratelimit-ip-limit"
    ] == "3"
    assert response.headers[
        "x-ratelimit-ip-remaining"
    ] == "2"


def test_user_limit_returns_native_429(
    rate_limit_http_context,
):
    context = rate_limit_http_context(
        user_limit=2,
        ip_limit=100,
    )

    for index in range(2):
        response = context["client"].get(
            "/auth/whoami",
            headers=request_headers(
                context,
                ip=(
                    f"203.0.113."
                    f"{index + 10}"
                ),
            ),
        )

        assert response.status_code == 200

    denied = context["client"].get(
        "/auth/whoami",
        headers=request_headers(
            context,
            ip="203.0.113.99",
        ),
    )

    assert denied.status_code == 429
    assert denied.json() == {
        "detail": {
            "code": (
                "user_rate_limit_exceeded"
            ),
            "message": (
                "User request rate limit "
                "exceeded"
            ),
        }
    }

    assert denied.headers[
        "retry-after"
    ] == "60"
    assert denied.headers[
        "x-ratelimit-scope"
    ] == "user"
    assert denied.headers[
        "x-ratelimit-limit"
    ] == "2"
    assert denied.headers[
        "x-ratelimit-remaining"
    ] == "0"


def test_ip_limit_returns_native_429(
    rate_limit_http_context,
):
    context = rate_limit_http_context(
        user_limit=100,
        ip_limit=2,
    )

    headers = request_headers(
        context,
        ip="198.51.100.20",
    )

    for _ in range(2):
        response = context["client"].get(
            "/auth/whoami",
            headers=headers,
        )

        assert response.status_code == 200

    denied = context["client"].get(
        "/auth/whoami",
        headers=headers,
    )

    assert denied.status_code == 429
    assert denied.json()["detail"][
        "code"
    ] == "ip_rate_limit_exceeded"
    assert denied.headers[
        "x-ratelimit-scope"
    ] == "ip"


def test_openai_route_uses_rate_limit_error(
    rate_limit_http_context,
):
    context = rate_limit_http_context(
        user_limit=1,
        ip_limit=100,
    )

    headers = request_headers(
        context,
        ip="192.0.2.10",
    )
    headers["Authorization"] = (
        f"Bearer {context['api_key']}"
    )
    headers.pop("X-API-Key")

    payload = {
        "provider": "mock",
        "model": "day10-model",
        "messages": [
            {
                "role": "user",
                "content": "day10",
            }
        ],
    }

    first = context["client"].post(
        "/v1/chat/completions",
        headers=headers,
        json=payload,
    )

    assert first.status_code == 200

    denied = context["client"].post(
        "/v1/chat/completions",
        headers=headers,
        json=payload,
    )

    assert denied.status_code == 429
    assert denied.json() == {
        "error": {
            "message": (
                "User request rate limit "
                "exceeded"
            ),
            "type": "rate_limit_error",
            "param": None,
            "code": (
                "user_rate_limit_exceeded"
            ),
        }
    }


def test_public_paths_are_not_limited(
    rate_limit_http_context,
):
    context = rate_limit_http_context(
        user_limit=1,
        ip_limit=1,
    )

    for _ in range(3):
        response = context[
            "client"
        ].get("/health")

        assert response.status_code == 200
        assert (
            "x-ratelimit-ip-limit"
            not in response.headers
        )


def test_authentication_failure_precedes_limit(
    rate_limit_http_context,
):
    context = rate_limit_http_context(
        user_limit=1,
        ip_limit=1,
    )

    response = context["client"].get(
        "/auth/whoami",
        headers=request_headers(
            context,
            ip="203.0.113.50",
            authenticated=False,
        ),
    )

    assert response.status_code == 401
    assert response.json()["detail"][
        "code"
    ] == "api_key_missing"
