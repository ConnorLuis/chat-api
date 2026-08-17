from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from src.app.llm.schemas import (
    ProviderExecutionTrace,
)


OpenAIMessageRole = Literal[
    "developer",
    "system",
    "user",
    "assistant",
]


class OpenAIChatMessage(BaseModel):
    """Day3 支持的纯文本 Chat Completion 消息子集。"""

    role: OpenAIMessageRole
    content: str

    model_config = ConfigDict(extra="forbid")


class OpenAIStreamOptions(BaseModel):
    """OpenAI-compatible streaming options."""

    include_usage: bool = False

    model_config = ConfigDict(extra="forbid")


class OpenAIChatCompletionRequest(BaseModel):
    """OpenAI-compatible Chat Completions 请求。

    当前支持纯文本、单 choice，以及非流式/流式调用。
    provider 是 chat-api 网关扩展字段。
    """

    model: str
    messages: list[OpenAIChatMessage] = Field(
        min_length=1,
    )

    provider: Literal[
        "mock",
        "ollama",
        "openai",
    ] | None = Field(
        default=None,
        description="chat-api gateway provider override.",
    )

    temperature: float | None = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
    )
    top_p: float | None = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
    )

    # 兼容传统 Chat Completions 客户端。
    max_tokens: int | None = Field(
        default=None,
        gt=0,
    )

    # 同时接受较新的 max_completion_tokens 参数。
    max_completion_tokens: int | None = Field(
        default=None,
        gt=0,
    )

    n: int = Field(
        default=1,
        ge=1,
    )
    stream: bool = False
    stream_options: OpenAIStreamOptions | None = None
    user: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("model must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_token_limit_fields(
        self,
    ) -> "OpenAIChatCompletionRequest":
        if (
            self.max_tokens is not None
            and self.max_completion_tokens is not None
        ):
            raise ValueError(
                "max_tokens and max_completion_tokens "
                "cannot both be set"
            )

        return self

    def resolved_max_tokens(self) -> int | None:
        if self.max_completion_tokens is not None:
            return self.max_completion_tokens
        return self.max_tokens


class OpenAICompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class OpenAIAssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class OpenAIChatCompletionChoice(BaseModel):
    index: int
    message: OpenAIAssistantMessage
    finish_reason: str | None = None
    logprobs: None = None


class OpenAIGatewayMetadata(BaseModel):
    """Optional chat-api extension; standard OpenAI fields stay intact."""

    provider_execution: ProviderExecutionTrace


class OpenAIChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[OpenAIChatCompletionChoice]
    usage: OpenAICompletionUsage | None = None
    gateway: OpenAIGatewayMetadata | None = None


class OpenAIChatCompletionDelta(BaseModel):
    """Streaming choice delta."""

    role: Literal["assistant"] | None = None
    content: str | None = None


class OpenAIChatCompletionChunkChoice(BaseModel):
    index: int
    delta: OpenAIChatCompletionDelta
    finish_reason: str | None = None
    logprobs: None = None


class OpenAIChatCompletionChunk(BaseModel):
    id: str
    object: Literal[
        "chat.completion.chunk"
    ] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[OpenAIChatCompletionChunkChoice]
    usage: OpenAICompletionUsage | None = None
    gateway: OpenAIGatewayMetadata | None = None


class OpenAIErrorDetail(BaseModel):
    message: str
    type: str
    param: str | None = None
    code: str | None = None


class OpenAIErrorResponse(BaseModel):
    error: OpenAIErrorDetail
    gateway: OpenAIGatewayMetadata | None = None
