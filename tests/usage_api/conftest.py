import pytest

from src.app.api.usage import (
    routes_usage as routes_module,
)
from src.app.db.base import Base
from src.app.db.session import (
    build_engine,
    build_session_factory,
)


@pytest.fixture(autouse=True)
def isolated_usage_api_db(
    tmp_path,
    monkeypatch,
):
    engine = build_engine(
        "sqlite:///"
        f"{tmp_path / 'usage_api.db'}"
    )

    Base.metadata.create_all(engine)

    session_factory = (
        build_session_factory(engine)
    )

    monkeypatch.setattr(
        routes_module,
        "get_session_factory",
        lambda: session_factory,
    )

    try:
        yield session_factory

    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
