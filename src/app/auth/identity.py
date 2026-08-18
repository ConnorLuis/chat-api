from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(
    frozen=True,
    slots=True,
)
class CallerIdentity:
    """认证成功后供路由和 Day10 使用的调用方身份."""

    key_id: str
    key_prefix: str
    key_name: str
    authenticated_at: datetime
    authentication_method: str
