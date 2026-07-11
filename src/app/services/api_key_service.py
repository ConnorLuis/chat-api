from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from src.app.auth.errors import (
    APIKeyNotFoundError,
    InvalidAPIKeyError,
    InvalidAPIKeyNameError,
    RevokedAPIKeyError,
)
from src.app.auth.identity import (
    CallerIdentity,
)
from src.app.auth.keys import (
    generate_api_key,
    parse_api_key,
    validate_pepper,
    verify_api_key,
)
from src.app.core.settings import settings
from src.app.db.models.api_key import (
    API_KEY_STATUS_ACTIVE,
    API_KEY_STATUS_REVOKED,
    APIKey,
)
from src.app.db.repositories import (
    APIKeyRepository,
)
from src.app.db.utils import utc_now


@dataclass(
    frozen=True,
    slots=True,
)
class CreatedAPIKey:
    """plaintext 只存在于创建结果中."""

    id: str
    api_key: str
    prefix: str
    name: str
    status: str
    created_at: datetime


class APIKeyService:
    def __init__(
        self,
        session: Session,
        *,
        pepper: str | None = None,
    ) -> None:
        self.session = session
        self.repository = (
            APIKeyRepository(session)
        )

        raw_pepper = (
            settings.API_KEY_HASH_PEPPER
            if pepper is None
            else pepper
        )

        self.pepper = validate_pepper(
            raw_pepper
        )

    @staticmethod
    def normalize_name(
        name: str,
    ) -> str:
        normalized = name.strip()

        if not normalized:
            raise InvalidAPIKeyNameError(
                "API key name must not "
                "be empty"
            )

        if len(normalized) > 120:
            raise InvalidAPIKeyNameError(
                "API key name must contain "
                "at most 120 characters"
            )

        return normalized

    def create_key(
        self,
        *,
        name: str,
        commit: bool = True,
    ) -> CreatedAPIKey:
        normalized_name = (
            self.normalize_name(name)
        )

        generated = generate_api_key(
            pepper=self.pepper
        )

        record = APIKey(
            prefix=generated.prefix,
            key_hash=generated.key_hash,
            name=normalized_name,
            status=API_KEY_STATUS_ACTIVE,
        )

        try:
            self.repository.add(record)

            if commit:
                self.session.commit()
                self.session.refresh(
                    record
                )

        except Exception:
            self.session.rollback()
            raise

        return CreatedAPIKey(
            id=record.id,
            api_key=generated.plaintext,
            prefix=record.prefix,
            name=record.name,
            status=record.status,
            created_at=record.created_at,
        )

    def authenticate(
        self,
        plaintext: str,
        *,
        authentication_method: str,
    ) -> CallerIdentity:
        parsed = parse_api_key(
            plaintext
        )

        if parsed is None:
            raise InvalidAPIKeyError(
                "Invalid API key"
            )

        record = (
            self.repository.get_by_prefix(
                parsed.prefix
            )
        )

        if record is None:
            raise InvalidAPIKeyError(
                "Invalid API key"
            )

        valid = verify_api_key(
            parsed.plaintext,
            expected_hash=record.key_hash,
            pepper=self.pepper,
        )

        if not valid:
            raise InvalidAPIKeyError(
                "Invalid API key"
            )

        if (
            record.status
            == API_KEY_STATUS_REVOKED
        ):
            raise RevokedAPIKeyError(
                "API key has been revoked"
            )

        if (
            record.status
            != API_KEY_STATUS_ACTIVE
        ):
            raise InvalidAPIKeyError(
                "Invalid API key status"
            )

        return CallerIdentity(
            key_id=record.id,
            key_prefix=record.prefix,
            key_name=record.name,
            authenticated_at=utc_now(),
            authentication_method=(
                authentication_method
            ),
        )

    def revoke_key(
        self,
        key_id: str,
        *,
        commit: bool = True,
    ) -> APIKey:
        record = (
            self.repository.get_by_id(
                key_id
            )
        )

        if record is None:
            raise APIKeyNotFoundError(
                "API key not found"
            )

        # 吊销操作保持幂等。
        if (
            record.status
            == API_KEY_STATUS_REVOKED
        ):
            return record

        record.status = (
            API_KEY_STATUS_REVOKED
        )
        record.revoked_at = utc_now()

        try:
            self.session.flush()

            if commit:
                self.session.commit()
                self.session.refresh(
                    record
                )

        except Exception:
            self.session.rollback()
            raise

        return record

    def list_keys(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[APIKey]:
        return self.repository.list_keys(
            limit=limit,
            offset=offset,
        )
