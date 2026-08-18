from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class ProviderMessage:
    """Provider 层统一消息结构。

    该结构只保留模型调用所需字段，不包含 RAG、PromptHub、
    conversation_id 等上层业务信息。
    """

    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ProviderChatRequest:
    """发送给具体模型 Provider 的统一请求。"""

    messages: tuple[ProviderMessage, ...]
    model: str | None = None
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int | None = 256


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    """统一 Token 用量边界。

    Day2 只建立结构；完整用量落库和成本计算放在 Chat-Day7 / Day8。
    """

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class ProviderAttempt:
    """一次实际下游 Provider 调用的可观测快照。"""

    ordinal: int
    provider: str
    model: str
    outcome: Literal[
        "succeeded",
        "failed",
        "stream_started",
        "stream_interrupted",
    ]
    latency_ms: int
    error_code: str | None = None
    retryable: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "provider": self.provider,
            "model": self.model,
            "outcome": self.outcome,
            "latency_ms": self.latency_ms,
            "error_code": self.error_code,
            "retryable": self.retryable,
        }


@dataclass(frozen=True, slots=True)
class ProviderExecutionMetadata:
    """一次网关请求的 retry/fallback 执行摘要。"""

    primary_provider: str
    final_provider: str
    attempts: tuple[ProviderAttempt, ...]
    retries: int
    fallback_used: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "primary_provider": self.primary_provider,
            "final_provider": self.final_provider,
            "total_attempts": len(self.attempts),
            "retries": self.retries,
            "fallback_used": self.fallback_used,
            "attempts": [
                attempt.as_dict()
                for attempt in self.attempts
            ],
        }


@dataclass(frozen=True, slots=True)
class ProviderChatResponse:
    """非流式 Provider 统一响应。"""

    content: str
    provider: str
    model: str
    usage: ProviderUsage | None = None
    finish_reason: str | None = None
    execution: ProviderExecutionMetadata | None = None
    raw_response: Any = field(
        default=None,
        repr=False,
        compare=False,
    )


@dataclass(frozen=True, slots=True)
class ProviderChatChunk:
    """流式 Provider 统一分片。"""

    delta: str
    provider: str
    model: str
    usage: ProviderUsage | None = None
    finish_reason: str | None = None
    execution: ProviderExecutionMetadata | None = None
    raw_chunk: Any = field(
        default=None,
        repr=False,
        compare=False,
    )
