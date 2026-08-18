import httpx
import pytest

from src.app.llm.providers import (
    ProviderConfigurationError,
    ProviderConnectionError,
    ProviderInvocationError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    normalize_provider_error,
)


def build_request() -> httpx.Request:
    return httpx.Request(
        "POST",
        "http://provider.test/chat",
    )


def build_status_error(
    status_code: int,
) -> httpx.HTTPStatusError:
    request = build_request()
    response = httpx.Response(
        status_code,
        request=request,
    )

    return httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=request,
        response=response,
    )


def test_maps_httpx_timeout_to_retryable_error():
    error = normalize_provider_error(
        "ollama",
        httpx.ReadTimeout(
            "read timed out",
            request=build_request(),
        ),
    )

    assert isinstance(error, ProviderTimeoutError)
    assert error.code == "provider_timeout"
    assert error.retryable is True
    assert error.provider == "ollama"


def test_maps_httpx_connection_failure_to_retryable_error():
    error = normalize_provider_error(
        "ollama",
        httpx.ConnectError(
            "connection refused",
            request=build_request(),
        ),
    )

    assert isinstance(error, ProviderConnectionError)
    assert error.retryable is True


@pytest.mark.parametrize(
    ("status_code", "expected_type", "retryable"),
    [
        (408, ProviderTimeoutError, True),
        (429, ProviderRateLimitError, True),
        (500, ProviderUnavailableError, True),
        (503, ProviderUnavailableError, True),
        (401, ProviderRequestError, False),
        (404, ProviderRequestError, False),
    ],
)
def test_maps_http_status_by_retry_semantics(
    status_code,
    expected_type,
    retryable,
):
    error = normalize_provider_error(
        "openai",
        build_status_error(status_code),
    )

    assert isinstance(error, expected_type)
    assert error.status_code == status_code
    assert error.retryable is retryable


def test_maps_openai_sdk_timeout_without_importing_sdk():
    api_timeout_error = type(
        "APITimeoutError",
        (RuntimeError,),
        {},
    )("sdk timeout")

    error = normalize_provider_error(
        "openai",
        api_timeout_error,
    )

    assert isinstance(error, ProviderTimeoutError)
    assert error.retryable is True


def test_unknown_error_is_not_retryable():
    error = normalize_provider_error(
        "ollama",
        RuntimeError("unexpected failure"),
    )

    assert isinstance(error, ProviderInvocationError)
    assert error.retryable is False


def test_existing_provider_error_is_preserved():
    original = ProviderConfigurationError(
        "missing configuration"
    )

    normalized = normalize_provider_error(
        "openai",
        original,
    )

    assert normalized is original
    assert normalized.provider == "openai"
    assert normalized.retryable is False
