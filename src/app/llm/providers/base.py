from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from .schemas import (
    ProviderChatChunk,
    ProviderChatRequest,
    ProviderChatResponse,
)


@runtime_checkable
class ChatProvider(Protocol):
    """所有聊天模型 Provider 必须满足的结构化协议。"""

    name: str

    def resolve_model(self, requested_model: str | None = None) -> str:
        """解析本次请求实际使用的模型名。"""
        ...

    def chat(
        self,
        request: ProviderChatRequest,
    ) -> ProviderChatResponse:
        """执行非流式聊天请求。"""
        ...

    def stream(
        self,
        request: ProviderChatRequest,
    ) -> AsyncIterator[ProviderChatChunk]:
        """执行流式聊天请求。"""
        ...
