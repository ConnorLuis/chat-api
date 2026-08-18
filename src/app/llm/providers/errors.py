from __future__ import annotations

from typing import Any

import httpx


class ChatProviderError(RuntimeError):
    """Provider 层异常基类。"""

    code = "provider_error"
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        status_code: int | None = None,
        execution: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.execution = execution


class UnsupportedProviderError(ChatProviderError):
    """请求了未支持的 Provider。"""

    code = "unsupported_provider"


class ProviderDependencyError(ChatProviderError):
    """Provider 所需可选依赖未安装。"""

    code = "provider_dependency_error"


class ProviderConfigurationError(ChatProviderError):
    """Provider 配置缺失或无效。"""

    code = "provider_configuration_error"


class ProviderInvocationError(ChatProviderError):
    """无法归入更具体类别的 Provider 调用错误。"""

    code = "provider_invocation_error"


class ProviderTimeoutError(ProviderInvocationError):
    """Provider 请求超时。"""

    code = "provider_timeout"
    retryable = True


class ProviderConnectionError(ProviderInvocationError):
    """Provider 网络连接失败。"""

    code = "provider_connection_error"
    retryable = True


class ProviderRateLimitError(ProviderInvocationError):
    """Provider 返回限流错误。"""

    code = "provider_rate_limited"
    retryable = True


class ProviderUnavailableError(ProviderInvocationError):
    """Provider 返回临时服务端错误。"""

    code = "provider_unavailable"
    retryable = True


class ProviderRequestError(ProviderInvocationError):
    """Provider 拒绝请求，重试通常不会成功。"""

    code = "provider_request_error"


class ProviderStreamInterruptedError(ProviderInvocationError):
    """流式响应已经输出 token 后发生异常。"""

    code = "provider_stream_interrupted"

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        status_code: int | None = None,
        execution: Any | None = None,
        cause_code: str | None = None,
    ) -> None:
        super().__init__(
            message,
            provider=provider,
            status_code=status_code,
            execution=execution,
        )
        self.cause_code = cause_code


def _exception_status_code(
    exc: BaseException,
) -> int | None:
    value = getattr(exc, "status_code", None)

    if value is None:
        response = getattr(exc, "response", None)
        value = getattr(response, "status_code", None)

    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _error_message(
    provider: str,
    category: str,
    exc: BaseException,
) -> str:
    detail = str(exc).strip() or type(exc).__name__
    return f"{provider} provider {category}: {detail}"


def normalize_provider_error(
    provider: str,
    exc: BaseException,
) -> ChatProviderError:
    """把 httpx/OpenAI SDK/未知异常映射为统一错误语义。"""

    if isinstance(exc, ChatProviderError):
        if exc.provider is None:
            exc.provider = provider
        return exc

    error_name = type(exc).__name__
    status_code = _exception_status_code(exc)

    if (
        isinstance(
            exc,
            (
                httpx.TimeoutException,
                TimeoutError,
            ),
        )
        or error_name == "APITimeoutError"
        or status_code == 408
    ):
        return ProviderTimeoutError(
            _error_message(provider, "timed out", exc),
            provider=provider,
            status_code=status_code,
        )

    if (
        isinstance(exc, httpx.NetworkError)
        or error_name == "APIConnectionError"
    ):
        return ProviderConnectionError(
            _error_message(
                provider,
                "connection failed",
                exc,
            ),
            provider=provider,
            status_code=status_code,
        )

    if (
        error_name == "RateLimitError"
        or status_code == 429
    ):
        return ProviderRateLimitError(
            _error_message(
                provider,
                "rate limited",
                exc,
            ),
            provider=provider,
            status_code=status_code,
        )

    if (
        error_name == "InternalServerError"
        or (
            status_code is not None
            and 500 <= status_code <= 599
        )
    ):
        return ProviderUnavailableError(
            _error_message(
                provider,
                "unavailable",
                exc,
            ),
            provider=provider,
            status_code=status_code,
        )

    if status_code is not None:
        return ProviderRequestError(
            _error_message(
                provider,
                f"rejected request with HTTP {status_code}",
                exc,
            ),
            provider=provider,
            status_code=status_code,
        )

    return ProviderInvocationError(
        _error_message(provider, "failed", exc),
        provider=provider,
    )
