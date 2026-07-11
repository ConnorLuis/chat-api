from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(
    frozen=True,
    slots=True,
)
class RateLimitPolicy:
    scope: str
    limit: int
    window_seconds: int

    def __post_init__(self) -> None:
        scope = self.scope.strip().lower()

        if not scope:
            raise ValueError(
                "scope must not be empty"
            )

        if self.limit < 1:
            raise ValueError(
                "limit must be greater "
                "than or equal to 1"
            )

        if self.window_seconds < 1:
            raise ValueError(
                "window_seconds must be "
                "greater than or equal to 1"
            )

        object.__setattr__(
            self,
            "scope",
            scope,
        )


@dataclass(
    frozen=True,
    slots=True,
)
class RateLimitDecision:
    scope: str
    subject: str
    allowed: bool
    limit: int
    remaining: int
    reset_at: datetime
    retry_after_seconds: int


@dataclass(
    frozen=True,
    slots=True,
)
class RequestRateLimitResult:
    user: RateLimitDecision | None
    ip: RateLimitDecision

    @property
    def decisions(
        self,
    ) -> tuple[RateLimitDecision, ...]:
        if self.user is None:
            return (self.ip,)

        return (
            self.user,
            self.ip,
        )

    @property
    def exceeded(
        self,
    ) -> RateLimitDecision | None:
        # 用户维度优先返回，更容易让调用方定位
        # 是哪一个 API Key 已达到请求限制。
        if (
            self.user is not None
            and not self.user.allowed
        ):
            return self.user

        if not self.ip.allowed:
            return self.ip

        return None
