from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .schemas import ProviderChatRequest, ProviderMessage


def to_provider_messages(
    messages: Iterable[Any],
) -> tuple[ProviderMessage, ...]:
    """把 Pydantic ChatMessage 等上层消息转换成 ProviderMessage。"""

    converted: list[ProviderMessage] = []

    for message in messages:
        role = str(getattr(message, "role", "user"))
        content = str(getattr(message, "content", ""))

        converted.append(
            ProviderMessage(
                role=role,
                content=content,
            )
        )

    return tuple(converted)


def build_provider_request(
    messages: Iterable[Any],
    *,
    model: str | None,
    temperature: float,
    top_p: float,
    max_tokens: int | None,
) -> ProviderChatRequest:
    """构建统一 Provider 请求。"""

    return ProviderChatRequest(
        messages=to_provider_messages(messages),
        model=model,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    )
