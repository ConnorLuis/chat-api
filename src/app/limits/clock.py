from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Return one timezone-aware instant."""


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)
