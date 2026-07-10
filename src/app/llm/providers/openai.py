from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from src.app.core.settings import settings

from .errors import (
    ProviderConfigurationError,
    ProviderDependencyError,
)
from .schemas import (
    ProviderChatChunk,
    ProviderChatRequest,
    ProviderChatResponse,
    ProviderUsage,
)


class OpenAIProvider:
    """OpenAI 和 OpenAI-compatible 服务的 Provider 边界。

    SDK 使用懒加载，基础 CI 不需要安装 openai。
    只有实际调用该 Provider 时才检查依赖和配置。
    """

    name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_s: float | None = None,
        settings_obj: Any = settings,
    ) -> None:
        self.api_key = (
            api_key
            if api_key is not None
            else settings_obj.OPENAI_API_KEY
        )
        self.base_url = (
            base_url
            if base_url is not None
            else settings_obj.OPENAI_BASE_URL
        )
        self.default_model = (
            model
            if model is not None
            else settings_obj.OPENAI_MODEL
        )
        self.timeout_s = float(
            timeout_s
            if timeout_s is not None
            else settings_obj.OPENAI_TIMEOUT_S
        )

    def resolve_model(self, requested_model: str | None = None) -> str:
        return requested_model or self.default_model or "unknown"

    def _validate_configuration(
        self,
        request: ProviderChatRequest,
    ) -> str:
        if not self.api_key:
            raise ProviderConfigurationError(
                "OPENAI_API_KEY is required when provider=openai."
            )

        model = self.resolve_model(request.model)
        if model == "unknown":
            raise ProviderConfigurationError(
                "OpenAI model is required. Set request.model "
                "or OPENAI_MODEL."
            )

        return model

    @staticmethod
    def _load_sync_client():
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderDependencyError(
                "OpenAIProvider requires the optional 'openai' package. "
                "Install it with: "
                "python -m pip install -r requirements-openai.txt"
            ) from exc

        return OpenAI

    @staticmethod
    def _load_async_client():
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ProviderDependencyError(
                "OpenAIProvider requires the optional 'openai' package. "
                "Install it with: "
                "python -m pip install -r requirements-openai.txt"
            ) from exc

        return AsyncOpenAI

    @staticmethod
    def _messages_payload(
        request: ProviderChatRequest,
    ) -> list[dict[str, str]]:
        return [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in request.messages
        ]

    def _request_kwargs(
        self,
        request: ProviderChatRequest,
        *,
        model: str,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._messages_payload(request),
            "temperature": request.temperature,
            "top_p": request.top_p,
        }

        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens

        return kwargs

    def _client_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "timeout": self.timeout_s,
        }

        if self.base_url:
            kwargs["base_url"] = self.base_url

        return kwargs

    @staticmethod
    def _usage_from_object(usage: Any) -> ProviderUsage | None:
        if usage is None:
            return None

        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(
            usage,
            "completion_tokens",
            None,
        )
        total_tokens = getattr(usage, "total_tokens", None)

        return ProviderUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    def chat(
        self,
        request: ProviderChatRequest,
    ) -> ProviderChatResponse:
        model = self._validate_configuration(request)
        OpenAI = self._load_sync_client()

        with OpenAI(**self._client_kwargs()) as client:
            response = client.chat.completions.create(
                **self._request_kwargs(
                    request,
                    model=model,
                )
            )

        choice = response.choices[0]
        content = choice.message.content or ""

        return ProviderChatResponse(
            content=content,
            provider=self.name,
            model=getattr(response, "model", None) or model,
            usage=self._usage_from_object(
                getattr(response, "usage", None)
            ),
            finish_reason=getattr(
                choice,
                "finish_reason",
                None,
            ),
            raw_response=response,
        )

    async def stream(
        self,
        request: ProviderChatRequest,
    ) -> AsyncIterator[ProviderChatChunk]:
        model = self._validate_configuration(request)
        AsyncOpenAI = self._load_async_client()
        client = AsyncOpenAI(**self._client_kwargs())

        try:
            stream = await client.chat.completions.create(
                **self._request_kwargs(
                    request,
                    model=model,
                ),
                stream=True,
            )

            async for chunk in stream:
                choices = getattr(chunk, "choices", None) or []
                usage = self._usage_from_object(
                    getattr(chunk, "usage", None)
                )

                if not choices:
                    if usage is not None:
                        yield ProviderChatChunk(
                            delta="",
                            provider=self.name,
                            model=(
                                getattr(chunk, "model", None)
                                or model
                            ),
                            usage=usage,
                            raw_chunk=chunk,
                        )
                    continue

                choice = choices[0]
                delta_obj = getattr(choice, "delta", None)
                content = (
                    getattr(delta_obj, "content", None)
                    if delta_obj is not None
                    else None
                )

                yield ProviderChatChunk(
                    delta=content or "",
                    provider=self.name,
                    model=getattr(chunk, "model", None) or model,
                    usage=usage,
                    finish_reason=getattr(
                        choice,
                        "finish_reason",
                        None,
                    ),
                    raw_chunk=chunk,
                )
        finally:
            await client.close()
