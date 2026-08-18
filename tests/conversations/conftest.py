from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.app.db.base import Base
from src.app.db.models import (
    Conversation,
    Message,
)
from src.app.db.session import (
    build_engine,
    build_session_factory,
    get_db_session,
)
from src.app.main import app


assert Conversation.__tablename__ == "conversations"
assert Message.__tablename__ == "messages"


@pytest.fixture
def conversation_session_factory(
    tmp_path,
):
    database_path = (
        tmp_path
        / "conversation_api_test.db"
    )

    engine = build_engine(
        f"sqlite:///{database_path}"
    )

    Base.metadata.create_all(engine)

    session_factory = (
        build_session_factory(engine)
    )

    try:
        yield session_factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def conversation_client(
    conversation_session_factory,
):
    def override_db_session():
        with conversation_session_factory() as session:
            yield session

    app.dependency_overrides[
        get_db_session
    ] = override_db_session

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(
            get_db_session,
            None,
        )
