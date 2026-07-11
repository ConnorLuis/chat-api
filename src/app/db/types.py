from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """跨 SQLite / PostgreSQL 保持 UTC 语义的时间类型."""

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(
        self,
        dialect: Dialect,
    ):
        return dialect.type_descriptor(
            DateTime(timezone=True)
        )

    def process_bind_param(
        self,
        value: datetime | None,
        dialect: Dialect,
    ) -> datetime | None:
        if value is None:
            return None

        if value.tzinfo is None:
            value = value.replace(
                tzinfo=timezone.utc,
            )

        value = value.astimezone(
            timezone.utc,
        )

        # SQLite 不保留 tzinfo，写入时使用 UTC naive，
        # 读取时再恢复为 UTC-aware。
        if dialect.name == "sqlite":
            return value.replace(
                tzinfo=None,
            )

        return value

    def process_result_value(
        self,
        value: datetime | None,
        dialect: Dialect,
    ) -> datetime | None:
        if value is None:
            return None

        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc,
            )

        return value.astimezone(
            timezone.utc,
        )
