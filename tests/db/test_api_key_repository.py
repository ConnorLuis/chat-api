from sqlalchemy import inspect

from src.app.db.models.api_key import (
    API_KEY_STATUS_ACTIVE,
    APIKey,
)
from src.app.db.repositories import (
    APIKeyRepository,
)


def test_api_key_repository_add_and_find(
    db_session,
):
    repository = APIKeyRepository(
        db_session
    )

    record = repository.add(
        APIKey(
            prefix="chat_sk_0123456789ab",
            key_hash="a" * 64,
            name="repository test",
            status=API_KEY_STATUS_ACTIVE,
        )
    )

    assert repository.get_by_id(
        record.id
    ) is record

    assert repository.get_by_prefix(
        record.prefix
    ) is record


def test_api_key_repository_lists_metadata(
    db_session,
):
    repository = APIKeyRepository(
        db_session
    )

    repository.add(
        APIKey(
            prefix="chat_sk_111111111111",
            key_hash="1" * 64,
            name="first",
        )
    )
    repository.add(
        APIKey(
            prefix="chat_sk_222222222222",
            key_hash="2" * 64,
            name="second",
        )
    )

    records = repository.list_keys()

    assert len(records) == 2
    assert {
        record.name
        for record in records
    } == {
        "first",
        "second",
    }


def test_api_key_schema_has_no_plaintext(
    db_engine,
):
    inspector = inspect(db_engine)

    columns = {
        column["name"]
        for column in inspector.get_columns(
            "api_keys"
        )
    }

    assert columns == {
        "id",
        "prefix",
        "key_hash",
        "name",
        "status",
        "created_at",
        "revoked_at",
    }

    assert "api_key" not in columns
    assert "plaintext" not in columns
    assert "secret" not in columns
