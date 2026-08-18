from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy.orm import Session

from src.app.db.session import (
    get_db_session,
)
from src.app.services import (
    ConversationNotFoundError,
    ConversationService,
)

from .schemas import (
    ConversationCreateRequest,
    ConversationDeleteResponse,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdateRequest,
    MessageListResponse,
)


router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
)


def _service(
    session: Session,
) -> ConversationService:
    return ConversationService(session)


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=201,
    summary="Create conversation",
)
def create_conversation(
    body: Annotated[
        ConversationCreateRequest,
        Body(),
    ],
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
):
    try:
        conversation = (
            _service(session)
            .create_conversation(
                title=body.title,
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return ConversationResponse.model_validate(
        conversation
    )


@router.get(
    "",
    response_model=ConversationListResponse,
    summary="List conversations",
)
def list_conversations(
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
    limit: Annotated[
        int,
        Query(ge=1, le=200),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
):
    conversations = (
        _service(session)
        .list_conversations(
            limit=limit,
            offset=offset,
        )
    )

    return ConversationListResponse(
        items=[
            ConversationResponse.model_validate(
                conversation
            )
            for conversation in conversations
        ],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get conversation",
)
def get_conversation(
    conversation_id: str,
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
):
    conversation = (
        _service(session)
        .get_conversation(
            conversation_id
        )
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    return ConversationResponse.model_validate(
        conversation
    )


@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Rename conversation",
)
def rename_conversation(
    conversation_id: str,
    body: Annotated[
        ConversationUpdateRequest,
        Body(),
    ],
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
):
    try:
        conversation = (
            _service(session)
            .rename_conversation(
                conversation_id,
                title=body.title,
            )
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return ConversationResponse.model_validate(
        conversation
    )


@router.delete(
    "/{conversation_id}",
    response_model=ConversationDeleteResponse,
    summary="Delete conversation",
)
def delete_conversation(
    conversation_id: str,
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
):
    deleted = (
        _service(session)
        .delete_conversation(
            conversation_id
        )
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    return ConversationDeleteResponse(
        id=conversation_id,
        deleted=True,
    )


@router.get(
    "/{conversation_id}/messages",
    response_model=MessageListResponse,
    summary="List conversation messages",
)
def list_conversation_messages(
    conversation_id: str,
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
    limit: Annotated[
        int,
        Query(ge=1, le=500),
    ] = 200,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
):
    try:
        messages = (
            _service(session)
            .list_messages(
                conversation_id,
                limit=limit,
                offset=offset,
            )
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        ) from exc

    return MessageListResponse(
        items=messages,
        limit=limit,
        offset=offset,
    )
