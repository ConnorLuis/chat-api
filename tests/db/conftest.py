from __future__ import annotations

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.app.db.base import Base
from src.app.db.models import (
    Conversation,
    Message,
    UsageCost,
    UsageRecord,
)
from src.app.db.session import (
    build_engine,
    build_session_factory,
)
from src.app.services import (
    ConversationService,
    UsageCostService,
    UsageService,
)


# 保证模型在 create_all 前注册。
assert Conversation.__tablename__ == "conversations"
assert Message.__tablename__ == "messages"
assert UsageCost.__tablename__ == "usage_costs"
assert UsageRecord.__tablename__ == "usage_records"


@pytest.fixture
def db_engine(
    tmp_path,
) -> Engine:
    database_path = (
        tmp_path
        / "chat_api_test.db"
    )

    database_url = (
        f"sqlite:///{database_path}"
    )

    engine = build_engine(
        database_url
    )

    Base.metadata.create_all(
        engine
    )

    try:
        yield engine
    finally:
        Base.metadata.drop_all(
            engine
        )
        engine.dispose()


@pytest.fixture
def db_session(
    db_engine: Engine,
) -> Session:
    session_factory = (
        build_session_factory(
            db_engine
        )
    )

    with session_factory() as session:
        try:
            yield session
        finally:
            session.rollback()


@pytest.fixture
def conversation_service(
    db_session: Session,
) -> ConversationService:
    return ConversationService(
        db_session
    )


@pytest.fixture
def usage_service(
    db_session: Session,
) -> UsageService:
    return UsageService(
        db_session
    )


@pytest.fixture
def usage_cost_service(
    db_session: Session,
) -> UsageCostService:
    return UsageCostService(
        db_session
    )
