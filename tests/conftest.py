import sys
from pathlib import Path


# 将项目根目录手动添加到 Python 的模块搜索路径（sys.path）中，解决测试文件（tests/ 目录下）无法直接导入项目源代码（src/ 目录下）的问题
"""
chat-api/          # 项目根目录（我们要添加到sys.path的目录）
├── src/           # 源代码目录
└── tests/         # 测试目录
    └── test_chat_mock.py  # 这段代码所在的测试文件
"""
# __file__是当前执行脚本文件路径，转换为Path对象，解析为绝对路径，获取当前路径的第一级父目录
ROOT = Path(__file__).resolve().parents[1]
# 将项目根目录加入搜索路径
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from src.app.main import app
import pytest

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def isolated_kb_env(tmp_path, monkeypatch):
    # 强制前置隔离，1.所有文件落盘在临时目录、2.强制使用Mock向量、3.接收参数：collection_name，实现测试间库隔离
    def _isolated_kb_env(collection_name: str):
        # 构造临时目录
        test_kb_root = tmp_path / "kb"
        test_chroma_dir = test_kb_root / "chroma"

        # 劫持环境变量 → 强制项目使用临时路径 + Mock 模型
        monkeypatch.setenv("KB_DIR", str(test_kb_root))
        monkeypatch.setenv("KB_CHROMA_DIR", str(test_chroma_dir))
        monkeypatch.setenv("KB_COLLECTION", collection_name)
        monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
        monkeypatch.setenv("EMBEDDING_DIM", "64")  # 小向量，测试超快

        # 返回临时路径（可选，测试里要用就拿）
        return {
            "kb_dir": test_kb_root,
            "chroma_dir": test_chroma_dir,
            "collection": collection_name
        }

    return _isolated_kb_env


# 某些历史测试直接使用模块级 TestClient(app)，
# 没有自行覆盖 get_session_factory。
# 为这些测试准备完整且隔离的默认数据库，
# 避免依赖仓库中的本地 SQLite 文件或预先执行 init_db。
import src.app.db.session as db_session_module
from src.app.db import models as _db_models  # noqa: F401
from src.app.db.base import Base
from src.app.db.session import (
    build_engine,
    build_session_factory,
    init_db,
)


@pytest.fixture(
    scope="session",
    autouse=True,
)
def isolated_default_database(
    tmp_path_factory,
):
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
