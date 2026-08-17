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


def test_provider_resilience_defaults(monkeypatch):
    keys = (
        "PROVIDER_RETRY_MAX_ATTEMPTS",
        "PROVIDER_RETRY_BASE_DELAY_MS",
        "PROVIDER_RETRY_MAX_DELAY_MS",
        "PROVIDER_FALLBACK_ENABLED",
        "PROVIDER_FALLBACK_PROVIDER",
        "PROVIDER_FALLBACK_MODEL",
    )

    for key in keys:
        monkeypatch.delenv(key, raising=False)

    settings = Settings()

    assert settings.PROVIDER_RETRY_MAX_ATTEMPTS == 2
    assert settings.PROVIDER_RETRY_BASE_DELAY_MS == 100
    assert settings.PROVIDER_RETRY_MAX_DELAY_MS == 1000
    assert settings.PROVIDER_FALLBACK_ENABLED is False
    assert settings.PROVIDER_FALLBACK_PROVIDER == ""
    assert settings.PROVIDER_FALLBACK_MODEL == ""


def test_provider_resilience_environment_overrides(monkeypatch):
    monkeypatch.setenv(
        "PROVIDER_RETRY_MAX_ATTEMPTS",
        "3",
    )
    monkeypatch.setenv(
        "PROVIDER_FALLBACK_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "PROVIDER_FALLBACK_PROVIDER",
        " OPENAI ",
    )
    monkeypatch.setenv(
        "PROVIDER_FALLBACK_MODEL",
        " fallback-model ",
    )

    settings = Settings()

    assert settings.PROVIDER_RETRY_MAX_ATTEMPTS == 3
    assert settings.PROVIDER_FALLBACK_ENABLED is True
    assert settings.PROVIDER_FALLBACK_PROVIDER == "openai"
    assert settings.PROVIDER_FALLBACK_MODEL == "fallback-model"


def test_non_positive_provider_timeout_is_rejected(monkeypatch):
    monkeypatch.setenv("OLLAMA_TIMEOUT_S", "0")

    with pytest.raises(ValueError, match="OLLAMA_TIMEOUT_S"):
        _ = Settings().OLLAMA_TIMEOUT_S
