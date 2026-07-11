from __future__ import annotations

from sqlalchemy.orm import Session

from src.app.db.models import Conversation, Message
from src.app.db.repositories import (
    ConversationRepository,
    MessageRepository,
)
from src.app.db.utils import utc_now

from .errors import (
    ConversationNotFoundError,
    InvalidMessageRoleError,
)


ALLOWED_MESSAGE_ROLES = frozenset({
    "developer",
    "system",
    "user",
    "assistant",
})


class ConversationService:
    """Conversation / Message 持久化业务边界."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session
        self.conversations = (
            ConversationRepository(session)
        )
        self.messages = MessageRepository(
            session
        )

    @staticmethod
    def _normalize_title(
        title: str | None,
    ) -> str | None:
        if title is None:
            return None

        normalized = title.strip()

        if not normalized:
            return None

        if len(normalized) > 200:
            raise ValueError(
                "title must contain at most 200 characters"
            )

        return normalized

    @staticmethod
    def _normalize_optional_text(
        value: str | None,
        *,
        field_name: str,
        max_length: int,
        lower: bool = False,
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip()

        if not normalized:
            return None

        if lower:
            normalized = normalized.lower()

        if len(normalized) > max_length:
            raise ValueError(
                f"{field_name} must contain at most "
                f"{max_length} characters"
            )

        return normalized

    @staticmethod
    def _validate_pagination(
        *,
        limit: int,
        offset: int,
        max_limit: int,
    ) -> None:
        if limit < 1 or limit > max_limit:
            raise ValueError(
                f"limit must be between 1 and {max_limit}"
            )

        if offset < 0:
            raise ValueError(
                "offset must be greater than or equal to 0"
            )

    def create_conversation(
        self,
        *,
        title: str | None = None,
    ) -> Conversation:
        normalized_title = self._normalize_title(
            title
        )

        try:
            conversation = self.conversations.create(
                title=normalized_title,
            )
            self.session.commit()
            self.session.refresh(
                conversation
            )
            return conversation
        except Exception:
            self.session.rollback()
            raise

    def get_conversation(
        self,
        conversation_id: str,
    ) -> Conversation | None:
        return self.conversations.get(
            conversation_id
        )

    def list_conversations(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Conversation]:
        self._validate_pagination(
            limit=limit,
            offset=offset,
            max_limit=200,
        )

        return self.conversations.list_conversations(
            limit=limit,
            offset=offset,
        )

    def rename_conversation(
        self,
        conversation_id: str,
        *,
        title: str | None,
    ) -> Conversation:
        normalized_title = self._normalize_title(
            title
        )

        try:
            conversation = (
                self.conversations.update_title(
                    conversation_id,
                    title=normalized_title,
                )
            )

            if conversation is None:
                raise ConversationNotFoundError(
                    f"Conversation not found: "
                    f"{conversation_id}"
                )

            conversation.updated_at = utc_now()

            self.session.commit()
            self.session.refresh(
                conversation
            )

            return conversation
        except Exception:
            self.session.rollback()
            raise

    def delete_conversation(
        self,
        conversation_id: str,
    ) -> bool:
        try:
            deleted = self.conversations.delete(
                conversation_id
            )
            self.session.commit()
            return deleted
        except Exception:
            self.session.rollback()
            raise

    def add_message(
        self,
        conversation_id: str,
        *,
        role: str,
        content: str,
        provider: str | None = None,
        model: str | None = None,
        token_count: int | None = None,
    ) -> Message:
        normalized_role = role.strip().lower()

        if normalized_role not in ALLOWED_MESSAGE_ROLES:
            supported = ", ".join(
                sorted(ALLOWED_MESSAGE_ROLES)
            )
            raise InvalidMessageRoleError(
                f"Unsupported message role: "
                f"{normalized_role}. "
                f"Supported roles: {supported}."
            )

        if not content.strip():
            raise ValueError(
                "content must not be empty"
            )

        if (
            token_count is not None
            and token_count < 0
        ):
            raise ValueError(
                "token_count must be greater than "
                "or equal to 0"
            )

        normalized_provider = (
            self._normalize_optional_text(
                provider,
                field_name="provider",
                max_length=50,
                lower=True,
            )
        )

        normalized_model = (
            self._normalize_optional_text(
                model,
                field_name="model",
                max_length=200,
            )
        )

        try:
            conversation = self.conversations.get(
                conversation_id
            )

            if conversation is None:
                raise ConversationNotFoundError(
                    f"Conversation not found: "
                    f"{conversation_id}"
                )

            message = self.messages.create(
                conversation_id=conversation_id,
                role=normalized_role,
                content=content,
                provider=normalized_provider,
                model=normalized_model,
                token_count=token_count,
            )

            conversation.updated_at = utc_now()

            self.session.commit()
            self.session.refresh(
                message
            )

            return message
        except Exception:
            self.session.rollback()
            raise

    def get_message(
        self,
        message_id: str,
    ) -> Message | None:
        return self.messages.get(
            message_id
        )

    def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> list[Message]:
        self._validate_pagination(
            limit=limit,
            offset=offset,
            max_limit=500,
        )

        if self.conversations.get(
            conversation_id
        ) is None:
            raise ConversationNotFoundError(
                f"Conversation not found: "
                f"{conversation_id}"
            )

        return self.messages.list_by_conversation(
            conversation_id,
            limit=limit,
            offset=offset,
        )

    def delete_message(
        self,
        message_id: str,
    ) -> bool:
        try:
            message = self.messages.get(
                message_id
            )

            if message is None:
                self.session.commit()
                return False

            conversation = self.conversations.get(
                message.conversation_id
            )

            deleted = self.messages.delete(
                message_id
            )

            if conversation is not None:
                conversation.updated_at = utc_now()

            self.session.commit()

            return deleted
        except Exception:
            self.session.rollback()
            raise
