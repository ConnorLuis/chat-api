from __future__ import annotations

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(
        default=None,
        max_length=200,
    )


class ConversationUpdateRequest(BaseModel):
    # PATCH 必须显式传 title，
    # 允许 null 表示清空标题。
    title: str | None = Field(
        max_length=200,
    )


class ConversationResponse(BaseModel):
    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    limit: int
    offset: int


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sequence_no: int
    role: str
    content: str
    provider: str | None
    model: str | None
    token_count: int | None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    limit: int
    offset: int


class ConversationDeleteResponse(BaseModel):
    id: str
    deleted: bool
