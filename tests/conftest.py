import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from src.app.main import app

import src.app.db.session as db_session_module
from src.app.db import models as _db_models  # noqa: F401
from src.app.db.base import Base
from src.app.db.session import (
    build_engine,
    build_session_factory,
    init_db,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def isolated_kb_env(
    tmp_path,
    monkeypatch,
):
    """为 KB / RAG 测试提供隔离目录和 Mock embedding."""

    def _isolated_kb_env(
        collection_name: str,
    ):
        test_kb_root = tmp_path / "kb"
        test_chroma_dir = (
            test_kb_root / "chroma"
        )

        monkeypatch.setenv(
            "KB_DIR",
            str(test_kb_root),
        )
        monkeypatch.setenv(
            "KB_CHROMA_DIR",
            str(test_chroma_dir),
        )
        monkeypatch.setenv(
            "KB_COLLECTION",
            collection_name,
        )
        monkeypatch.setenv(
            "EMBEDDING_PROVIDER",
            "mock",
        )
        monkeypatch.setenv(
            "EMBEDDING_DIM",
            "64",
        )

        return {
            "kb_dir": test_kb_root,
            "chroma_dir": test_chroma_dir,
            "collection": collection_name,
        }

    return _isolated_kb_env


@pytest.fixture(autouse=True)
def disable_api_auth_by_default(
    monkeypatch,
):
    """历史测试默认关闭认证；认证专项测试显式重新开启."""

    monkeypatch.delenv(
        "API_AUTH_ENABLED",
        raising=False,
    )
    monkeypatch.delenv(
        "API_KEY_HASH_PEPPER",
        raising=False,
    )
    monkeypatch.delenv(
        "CHAT_API_KEY",
        raising=False,
    )


@pytest.fixture(
    scope="session",
    autouse=True,
)
def isolated_default_database(
    tmp_path_factory,
):
    """为模块级 TestClient 提供完整隔离数据库."""

    database_dir = (
        tmp_path_factory.mktemp(
            "default_database"
        )
    )
    database_path = (
        database_dir
        / "chat_api_test.db"
    )

    engine = build_engine(
        f"sqlite:///{database_path}"
    )
    session_factory = (
        build_session_factory(engine)
    )

    original_engine = (
        db_session_module
        ._default_engine
    )
    original_session_factory = (
        db_session_module
        ._default_session_factory
    )

    db_session_module._default_engine = (
        engine
    )
    db_session_module._default_session_factory = (
        session_factory
    )

    init_db(engine)

    try:
        yield session_factory

    finally:
        db_session_module._default_session_factory = (
            original_session_factory
        )
        db_session_module._default_engine = (
            original_engine
        )

        Base.metadata.drop_all(engine)
        engine.dispose()
