import pytest

from src.app.auth import (
    APIKeyConfigurationError,
    InvalidAPIKeyError,
    InvalidAPIKeyNameError,
    RevokedAPIKeyError,
)
from src.app.db.models import APIKey
from src.app.db.models.api_key import (
    API_KEY_STATUS_REVOKED,
)
from src.app.services import (
    APIKeyService,
)


PEPPER = (
    "day9-test-pepper-"
    "0123456789abcdef0123456789abcdef"
)


def test_create_returns_plaintext_once_and_authenticates(
    db_session,
):
    service = APIKeyService(
        db_session,
        pepper=PEPPER,
    )

    created = service.create_key(
        name="local development"
    )

    assert created.api_key.startswith(
        created.prefix + "_"
    )

    record = db_session.get(
        APIKey,
        created.id,
    )

    assert record is not None
    assert record.prefix == (
        created.prefix
    )
    assert record.key_hash != (
        created.api_key
    )
    assert created.api_key not in (
        record.key_hash
    )

    identity = service.authenticate(
        created.api_key,
        authentication_method=(
            "x-api-key"
        ),
    )

    assert identity.key_id == created.id
    assert identity.key_prefix == (
        created.prefix
    )
    assert identity.key_name == (
        "local development"
    )
    assert (
        identity.authentication_method
        == "x-api-key"
    )


def test_wrong_secret_is_invalid(
    db_session,
):
    service = APIKeyService(
        db_session,
        pepper=PEPPER,
    )

    created = service.create_key(
        name="wrong secret"
    )

    wrong_key = (
        created.api_key[:-1]
        + (
            "A"
            if created.api_key[-1] != "A"
            else "B"
        )
    )

    with pytest.raises(
        InvalidAPIKeyError
    ):
        service.authenticate(
            wrong_key,
            authentication_method=(
                "bearer"
            ),
        )


def test_unknown_prefix_is_invalid(
    db_session,
):
    service = APIKeyService(
        db_session,
        pepper=PEPPER,
    )

    unknown = (
        "chat_sk_ffffffffffff_"
        + "A" * 43
    )

    with pytest.raises(
        InvalidAPIKeyError
    ):
        service.authenticate(
            unknown,
            authentication_method=(
                "bearer"
            ),
        )


def test_revoke_sets_status_and_time(
    db_session,
):
    service = APIKeyService(
        db_session,
        pepper=PEPPER,
    )

    created = service.create_key(
        name="revoke test"
    )

    revoked = service.revoke_key(
        created.id
    )

    assert revoked.status == (
        API_KEY_STATUS_REVOKED
    )
    assert revoked.revoked_at is not None

    with pytest.raises(
        RevokedAPIKeyError
    ):
        service.authenticate(
            created.api_key,
            authentication_method=(
                "x-api-key"
            ),
        )


def test_revoke_is_idempotent(
    db_session,
):
    service = APIKeyService(
        db_session,
        pepper=PEPPER,
    )

    created = service.create_key(
        name="idempotent revoke"
    )

    first = service.revoke_key(
        created.id
    )
    first_revoked_at = (
        first.revoked_at
    )

    second = service.revoke_key(
        created.id
    )

    assert second.revoked_at == (
        first_revoked_at
    )


def test_invalid_name_is_rejected(
    db_session,
):
    service = APIKeyService(
        db_session,
        pepper=PEPPER,
    )

    with pytest.raises(
        InvalidAPIKeyNameError
    ):
        service.create_key(name="   ")


def test_short_pepper_is_rejected(
    db_session,
):
    with pytest.raises(
        APIKeyConfigurationError
    ):
        APIKeyService(
            db_session,
            pepper="too-short",
        )
