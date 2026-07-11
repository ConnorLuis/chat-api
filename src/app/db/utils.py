from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


def new_uuid() -> str:
    """生成可安全暴露给外部 API 的 UUID 字符串."""

    return str(uuid4())


def utc_now() -> datetime:
    """返回 timezone-aware UTC 时间."""

    return datetime.now(timezone.utc)
