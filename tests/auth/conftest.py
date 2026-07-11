from __future__ import annotations

import pytest
from fastapi.testclient import (
    TestClient,
)

import src.app.db.session as db_session_module
from src.app.db.base import Base
from src.app.db.session import (
    build_engine,
    build_session_factory,
)
from src.app.main import app
from src.app.services import (
    APIKeyService,
)


TEST_PEPPER = (
    "day9-http-test-pepper-"
    "0123456789abcdef0123456789abcdef"
)


@pytest.fixture
def auth_context(
    tmp_path,
    monkeypatch,
    disable_api_auth_by_default,
):
    database_path = (
        tmp_path
        / "auth_test.db"
    )

    engine = build_engine(
        f"sqlite:///{database_path}"
    )
    session_factory = (
        build_session_factory(engine)
    )

    Base.metadata.create_all(engine)

    original_engine = (
        db_session_module
        ._default_engine
    )
    original_factory = (
        db_session_module
        ._default_session_factory
    )

    db_session_module._default_engine = (
        engine
    )
    db_session_module._default_session_factory = (
        session_factory
    )

    monkeypatch.setenv(
        "API_AUTH_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "API_KEY_HASH_PEPPER",
        TEST_PEPPER,
    )

    with session_factory() as session:
        created = APIKeyService(
            session,
            pepper=TEST_PEPPER,
        ).create_key(
            name="http test key"
        )

    try:
        yield {
            "client": TestClient(app),
            "api_key": created.api_key,
            "key_id": created.id,
            "prefix": created.prefix,
            "name": created.name,
            "session_factory": (
                session_factory
            ),
        }

    finally:
        db_session_module._default_session_factory = (
            original_factory
        )
        db_session_module._default_engine = (
            original_engine
        )

        Base.metadata.drop_all(engine)
        engine.dispose()
