from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from .schemas import (
    ProviderChatChunk,
    ProviderChatRequest,
    ProviderChatResponse,
)


class MockProvider:
    """CI、契约测试和前端联调用的确定性 Provider。"""

    name = "mock"
    default_model = "unknown"

    def resolve_model(self, requested_model: str | None = None) -> str:
        return requested_model or self.default_model

    @staticmethod
    def _last_user_content(request: ProviderChatRequest) -> str:
        for message in reversed(request.messages):
            if message.role == "user":
                return message.content
        return ""

    def chat(
        self,
        request: ProviderChatRequest,
    ) -> ProviderChatResponse:
        last_user = self._last_user_content(request)
        content = f"[mock] you said: {last_user[:200]}"

        return ProviderChatResponse(
            content=content,
            provider=self.name,
            model=self.resolve_model(request.model),
            finish_reason="stop",
        )

    async def stream(
        self,
        request: ProviderChatRequest,
    ) -> AsyncIterator[ProviderChatChunk]:
        response = self.chat(request)
        stream_text = f"[mock-stream] {response.content}"

        for character in stream_text:
            yield ProviderChatChunk(
                delta=character,
                provider=self.name,
                model=response.model,
            )
            await asyncio.sleep(0.01)
