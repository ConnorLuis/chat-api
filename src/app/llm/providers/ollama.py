from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from src.app.core.settings import settings

from .schemas import (
    ProviderChatChunk,
    ProviderChatRequest,
    ProviderChatResponse,
    ProviderUsage,
)


class OllamaProvider:
    """Ollama 模型 Provider。

    Day2 保留旧项目使用的 /api/generate 协议，
    避免 Provider 重构与模型协议切换同时发生。
    """

    name = "ollama"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout_s: float | None = None,
        settings_obj: Any = settings,
    ) -> None:
        self.base_url = base_url or settings_obj.OLLAMA_BASE_URL
        self.default_model = model or settings_obj.OLLAMA_MODEL
        self.timeout_s = float(
            timeout_s
            if timeout_s is not None
            else settings_obj.OLLAMA_TIMEOUT_S
        )

    def resolve_model(self, requested_model: str | None = None) -> str:
        return requested_model or self.default_model or "unknown"

    @staticmethod
    def _to_prompt(request: ProviderChatRequest) -> str:
        return "\n".join(
            f"{message.role}: {message.content}"
            for message in request.messages
        )

    def _build_payload(
        self,
        request: ProviderChatRequest,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        options: dict[str, Any] = {
            "temperature": request.temperature,
            "top_p": request.top_p,
        }

        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens

        return {
            "model": self.resolve_model(request.model),
            "prompt": self._to_prompt(request),
            "stream": stream,
            "options": options,
        }

    @staticmethod
    def _usage_from_payload(
        payload: dict[str, Any],
    ) -> ProviderUsage | None:
        prompt_tokens = payload.get("prompt_eval_count")
        completion_tokens = payload.get("eval_count")

        if prompt_tokens is None and completion_tokens is None:
            return None

        total_tokens = (
            int(prompt_tokens or 0)
            + int(completion_tokens or 0)
        )

        return ProviderUsage(
            prompt_tokens=(
                int(prompt_tokens)
                if prompt_tokens is not None
                else None
            ),
            completion_tokens=(
                int(completion_tokens)
                if completion_tokens is not None
                else None
            ),
            total_tokens=total_tokens,
        )

    def chat(
        self,
        request: ProviderChatRequest,
    ) -> ProviderChatResponse:
        payload = self._build_payload(request, stream=False)

        with httpx.Client(timeout=self.timeout_s) as client:
            response = client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        return ProviderChatResponse(
            content=data.get("response", ""),
            provider=self.name,
            model=data.get("model") or payload["model"],
            usage=self._usage_from_payload(data),
            finish_reason=(
                data.get("done_reason")
                or ("stop" if data.get("done") else None)
            ),
            raw_response=data,
        )

    async def stream(
        self,
        request: ProviderChatRequest,
    ) -> AsyncIterator[ProviderChatChunk]:
        payload = self._build_payload(request, stream=True)
        model = payload["model"]

        async with httpx.AsyncClient(
            timeout=self.timeout_s,
        ) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json=payload,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                    except (TypeError, ValueError):
                        continue

                    delta = data.get("response", "")
                    done = bool(data.get("done"))

                    if delta:
                        yield ProviderChatChunk(
                            delta=delta,
                            provider=self.name,
                            model=data.get("model") or model,
                            raw_chunk=data,
                        )

                    if done:
                        usage = self._usage_from_payload(data)

                        if usage is not None or data.get("done_reason"):
                            yield ProviderChatChunk(
                                delta="",
                                provider=self.name,
                                model=data.get("model") or model,
                                usage=usage,
                                finish_reason=(
                                    data.get("done_reason") or "stop"
                                ),
                                raw_chunk=data,
                            )
                        break
