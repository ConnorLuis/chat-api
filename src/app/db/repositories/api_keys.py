from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.app.db.models import APIKey


class APIKeyRepository:
    """APIKey persistence boundary."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def add(
        self,
        api_key: APIKey,
    ) -> APIKey:
        self.session.add(api_key)
        self.session.flush()

        return api_key

    def get_by_id(
        self,
        key_id: str,
    ) -> APIKey | None:
        return self.session.get(
            APIKey,
            key_id,
        )

    def get_by_prefix(
        self,
        prefix: str,
    ) -> APIKey | None:
        statement = select(APIKey).where(
            APIKey.prefix == prefix
        )

        return self.session.scalar(
            statement
        )

    def list_keys(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[APIKey]:
        statement = (
            select(APIKey)
            .order_by(
                APIKey.created_at.desc(),
                APIKey.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        return list(
            self.session.scalars(
                statement
            ).all()
        )
