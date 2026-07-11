from __future__ import annotations

from src.app.auth.identity import (
    CallerIdentity,
)

from .clock import (
    Clock,
    SystemClock,
)
from .models import (
    RateLimitDecision,
    RateLimitPolicy,
    RequestRateLimitResult,
)
from .store import (
    InMemorySlidingWindowStore,
)


USER_RATE_LIMIT_SCOPE = "user"
IP_RATE_LIMIT_SCOPE = "ip"


class RequestRateLimitService:
    def __init__(
        self,
        *,
        user_policy: RateLimitPolicy,
        ip_policy: RateLimitPolicy,
        store: (
            InMemorySlidingWindowStore
            | None
        ) = None,
        clock: Clock | None = None,
    ) -> None:
        if (
            user_policy.scope
            != USER_RATE_LIMIT_SCOPE
        ):
            raise ValueError(
                "user policy scope must "
                "be user"
            )

        if (
            ip_policy.scope
            != IP_RATE_LIMIT_SCOPE
        ):
            raise ValueError(
                "IP policy scope must be ip"
            )

        self.user_policy = user_policy
        self.ip_policy = ip_policy
        self.store = (
            store
            or InMemorySlidingWindowStore()
        )
        self.clock = (
            clock
            or SystemClock()
        )

    def check_user(
        self,
        caller: CallerIdentity | None,
    ) -> RateLimitDecision | None:
        if caller is None:
            return None

        return self.store.consume(
            policy=self.user_policy,
            subject=caller.key_id,
            now=self.clock.now(),
        )

    def check_ip(
        self,
        client_ip: str,
    ) -> RateLimitDecision:
        return self.store.consume(
            policy=self.ip_policy,
            subject=client_ip,
            now=self.clock.now(),
        )

    def check_request(
        self,
        *,
        caller: CallerIdentity | None,
        client_ip: str,
    ) -> RequestRateLimitResult:
        entries = []

        if caller is not None:
            entries.append((
                self.user_policy,
                caller.key_id,
            ))

        entries.append((
            self.ip_policy,
            client_ip,
        ))

        decisions = self.store.consume_many(
            entries=entries,
            now=self.clock.now(),
        )

        if caller is None:
            return RequestRateLimitResult(
                user=None,
                ip=decisions[0],
            )

        return RequestRateLimitResult(
            user=decisions[0],
            ip=decisions[1],
        )
