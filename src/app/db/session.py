from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from src.app.core.settings import settings

from .base import Base


SessionFactory = sessionmaker[Session]

_default_engine: Engine | None = None
_default_session_factory: SessionFactory | None = None


def _ensure_sqlite_parent(
    database_url: str,
) -> None:
    url = make_url(database_url)

    if url.get_backend_name() != "sqlite":
        return

    database = url.database

    if (
        not database
        or database == ":memory:"
        or database.startswith("file:")
    ):
        return

    Path(database).expanduser().parent.mkdir(
        parents=True,
        exist_ok=True,
    )


def build_engine(
    database_url: str,
    *,
    echo: bool = False,
) -> Engine:
    """构造可用于 SQLite 或 PostgreSQL 的 Engine."""

    url = make_url(database_url)
    backend = url.get_backend_name()

    _ensure_sqlite_parent(
        database_url,
    )

    connect_args: dict[str, Any] = {}

    if backend == "sqlite":
        connect_args["check_same_thread"] = False

    engine = create_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
        connect_args=connect_args,
    )

    if backend == "sqlite":

        @event.listens_for(
            engine,
            "connect",
        )
        def enable_sqlite_foreign_keys(
            dbapi_connection: Any,
            _connection_record: Any,
        ) -> None:
            cursor = dbapi_connection.cursor()

            try:
                cursor.execute(
                    "PRAGMA foreign_keys=ON"
                )
            finally:
                cursor.close()

    return engine


def build_session_factory(
    engine: Engine,
) -> SessionFactory:
    """构造同步 Session factory.

    Repository 负责 flush/query，Service 负责 commit/rollback。
    """

    return sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )


def get_engine() -> Engine:
    """懒加载默认 Engine，避免 import 时创建本地数据库."""

    global _default_engine

    if _default_engine is None:
        _default_engine = build_engine(
            settings.DATABASE_URL
        )

    return _default_engine


def get_session_factory() -> SessionFactory:
    """懒加载应用默认 Session factory."""

    global _default_session_factory

    if _default_session_factory is None:
        _default_session_factory = (
            build_session_factory(
                get_engine()
            )
        )

    return _default_session_factory


def init_db(
    engine: Engine | None = None,
) -> None:
    """开发环境 schema bootstrap.

    正式 PostgreSQL schema 迁移后续交给 Alembic；
    Day5 暂时只提供 create_all 初始化边界。
    """

    # 导入模型，确保它们注册到 Base.metadata。
    from . import models as _models  # noqa: F401

    target_engine = engine or get_engine()

    Base.metadata.create_all(
        bind=target_engine
    )


def get_db_session() -> Generator[
    Session,
    None,
    None,
]:
    """未来 FastAPI route 可复用的 Session dependency."""

    session_factory = get_session_factory()

    with session_factory() as session:
        yield session
