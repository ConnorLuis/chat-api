import pytest

from src.app.core.settings import Settings


def test_portable_provider_defaults(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)

    settings = Settings()

    assert settings.OLLAMA_BASE_URL == "http://127.0.0.1:11434"
    assert (
        settings.EMBEDDING_MODEL
        == "maidalun1020/bce-embedding-base_v1"
    )


def test_empty_values_fall_back_to_portable_defaults(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "")
    monkeypatch.setenv("EMBEDDING_MODEL", "")

    settings = Settings()

    assert settings.OLLAMA_BASE_URL == "http://127.0.0.1:11434"
    assert (
        settings.EMBEDDING_MODEL
        == "maidalun1020/bce-embedding-base_v1"
    )


def test_environment_values_override_defaults(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test:11434")
    monkeypatch.setenv("EMBEDDING_MODEL", "/models/local-embedding")

    settings = Settings()

    assert settings.OLLAMA_BASE_URL == "http://ollama.test:11434"
    assert settings.EMBEDDING_MODEL == "/models/local-embedding"


def test_invalid_auth_boolean_is_rejected(monkeypatch):
    monkeypatch.setenv("API_AUTH_ENABLED", "sometimes")

    with pytest.raises(ValueError, match="API_AUTH_ENABLED"):
        _ = Settings().API_AUTH_ENABLED
