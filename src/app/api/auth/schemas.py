from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CallerIdentityResponse(
    BaseModel
):
    authenticated: bool
    auth_enabled: bool

    key_id: str | None = None
    key_prefix: str | None = None
    key_name: str | None = None

    authentication_method: (
        str | None
    ) = None

    authenticated_at: (
        datetime | None
    ) = None
