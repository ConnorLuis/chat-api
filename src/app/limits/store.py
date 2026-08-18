from __future__ import annotations

from collections import (
    defaultdict,
    deque,
)
from datetime import (
    datetime,
    timezone,
)
from math import ceil
from threading import RLock

from .models import (
    RateLimitDecision,
    RateLimitPolicy,
)


class InMemorySlidingWindowStore:
    """Thread-safe single-process rate store.

    同一次请求涉及多个 scope 时使用 consume_many，
    保证要么所有维度同时消费，要么全部不消费。

    多实例生产部署必须替换为 Redis 等共享存储。
    """

    def __init__(self) -> None:
        self._events: dict[
            tuple[str, str],
            deque[float],
        ] = defaultdict(deque)

        self._lock = RLock()

    @staticmethod
    def _normalize_subject(
        subject: str,
    ) -> str:
        normalized = subject.strip()

        if not normalized:
            raise ValueError(
                "subject must not be empty"
            )

        if len(normalized) > 512:
            raise ValueError(
                "subject must contain at most "
                "512 characters"
            )

        return normalized

    @staticmethod
    def _validate_now(
        now: datetime,
    ) -> None:
        if (
            now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise ValueError(
                "now must be timezone-aware"
            )

    @staticmethod
    def _reset_timestamp(
        *,
        events: deque[float],
        timestamp: float,
        window_seconds: int,
    ) -> float:
        if events:
            return (
                events[0]
                + window_seconds
            )

        return (
            timestamp
            + window_seconds
        )

    def consume_many(
        self,
        *,
        entries: list[
            tuple[
                RateLimitPolicy,
                str,
            ]
        ],
        now: datetime,
    ) -> list[RateLimitDecision]:
        self._validate_now(now)

        if not entries:
            return []

        timestamp = now.timestamp()

        normalized_entries = []
        seen_keys: set[
            tuple[str, str]
        ] = set()

        for policy, subject in entries:
            normalized_subject = (
                self._normalize_subject(
                    subject
                )
            )
            key = (
                policy.scope,
                normalized_subject,
            )

            if key in seen_keys:
                raise ValueError(
                    "duplicate rate limit "
                    "scope and subject"
                )

            seen_keys.add(key)

            normalized_entries.append((
                policy,
                normalized_subject,
                key,
            ))

        with self._lock:
            prepared = []

            for (
                policy,
                subject,
                key,
            ) in normalized_entries:
                events = self._events[key]
                cutoff = (
                    timestamp
                    - policy.window_seconds
                )

                while (
                    events
                    and events[0] <= cutoff
                ):
                    events.popleft()

                prepared.append((
                    policy,
                    subject,
                    events,
                ))

            any_denied = any(
                len(events) >= policy.limit
                for (
                    policy,
                    _subject,
                    events,
                ) in prepared
            )

            decisions = []

            for (
                policy,
                subject,
                events,
            ) in prepared:
                reset_timestamp = (
                    self._reset_timestamp(
                        events=events,
                        timestamp=timestamp,
                        window_seconds=(
                            policy.window_seconds
                        ),
                    )
                )

                if len(events) >= policy.limit:
                    retry_after = max(
                        1,
                        ceil(
                            reset_timestamp
                            - timestamp
                        ),
                    )

                    decisions.append(
                        RateLimitDecision(
                            scope=policy.scope,
                            subject=subject,
                            allowed=False,
                            limit=policy.limit,
                            remaining=0,
                            reset_at=(
                                datetime
                                .fromtimestamp(
                                    reset_timestamp,
                                    tz=timezone.utc,
                                )
                            ),
                            retry_after_seconds=(
                                retry_after
                            ),
                        )
                    )

                    continue

                if any_denied:
                    # 整个请求未被 admission，
                    # 此 scope 不能单独消费一次。
                    decisions.append(
                        RateLimitDecision(
                            scope=policy.scope,
                            subject=subject,
                            allowed=True,
                            limit=policy.limit,
                            remaining=(
                                policy.limit
                                - len(events)
                            ),
                            reset_at=(
                                datetime
                                .fromtimestamp(
                                    reset_timestamp,
                                    tz=timezone.utc,
                                )
                            ),
                            retry_after_seconds=0,
                        )
                    )

                    continue

                events.append(timestamp)

                reset_timestamp = (
                    events[0]
                    + policy.window_seconds
                )

                decisions.append(
                    RateLimitDecision(
                        scope=policy.scope,
                        subject=subject,
                        allowed=True,
                        limit=policy.limit,
                        remaining=(
                            policy.limit
                            - len(events)
                        ),
                        reset_at=(
                            datetime.fromtimestamp(
                                reset_timestamp,
                                tz=timezone.utc,
                            )
                        ),
                        retry_after_seconds=0,
                    )
                )

            return decisions

    def consume(
        self,
        *,
        policy: RateLimitPolicy,
        subject: str,
        now: datetime,
    ) -> RateLimitDecision:
        return self.consume_many(
            entries=[
                (
                    policy,
                    subject,
                )
            ],
            now=now,
        )[0]

    def clear(
        self,
        *,
        scope: str,
        subject: str,
    ) -> None:
        key = (
            scope.strip().lower(),
            self._normalize_subject(
                subject
            ),
        )

        with self._lock:
            self._events.pop(
                key,
                None,
            )

    def clear_all(self) -> None:
        with self._lock:
            self._events.clear()
