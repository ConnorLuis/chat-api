from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.app.conversations import ContextMessage
from src.app.db.models import (
    UsageCost,
    UsageRecord,
)
from src.app.db.session import SessionFactory
from src.app.services import (
    ConversationService,
    NewMessage,
    NewUsageRecord,
    UsageCostService,
    UsageService,
)


@dataclass(
    frozen=True,
    slots=True,
)
class UsagePersistenceResult:
    usage_record: UsageRecord
    usage_cost: UsageCost

    @property
    def request_id(self) -> str:
        """兼容 Day7 路由中对 request_id 的直接访问."""

        return self.usage_record.request_id


def persist_usage_only(
    *,
    session_factory: SessionFactory,
    usage: NewUsageRecord,
) -> UsagePersistenceResult:
    """原子持久化 UsageRecord 与 UsageCost."""

    with session_factory() as session:
        try:
            usage_record = UsageService(
                session
            ).record_usage(
                usage,
                commit=False,
            )

            usage_cost = UsageCostService(
                session
            ).record_cost_for_usage(
                usage_record,
                commit=False,
            )

            session.commit()
            session.refresh(usage_record)
            session.refresh(usage_cost)

            return UsagePersistenceResult(
                usage_record=usage_record,
                usage_cost=usage_cost,
            )

        except Exception:
            session.rollback()
            raise


def persist_sync_exchange_and_usage(
    *,
    session_factory: SessionFactory,
    conversation_id: str | None,
    request_messages: Sequence[ContextMessage],
    assistant_content: str,
    provider: str,
    model: str,
    assistant_token_count: int | None,
    usage: NewUsageRecord,
) -> UsagePersistenceResult:
    """原子持久化消息、UsageRecord 和 UsageCost.

    conversation_id 为空时不保存 Message，
    但仍保存请求级 usage/cost。
    """

    with session_factory() as session:
        try:
            if conversation_id is not None:
                new_messages = [
                    NewMessage(
                        role=message.role,
                        content=message.content,
                    )
                    for message in request_messages
                ]

                new_messages.append(
                    NewMessage(
                        role="assistant",
                        content=assistant_content,
                        provider=provider,
                        model=model,
                        token_count=(
                            assistant_token_count
                        ),
                    )
                )

                ConversationService(
                    session
                ).append_messages(
                    conversation_id,
                    messages=new_messages,
                    commit=False,
                )

            usage_record = UsageService(
                session
            ).record_usage(
                usage,
                commit=False,
            )

            usage_cost = UsageCostService(
                session
            ).record_cost_for_usage(
                usage_record,
                commit=False,
            )

            session.commit()
            session.refresh(usage_record)
            session.refresh(usage_cost)

            return UsagePersistenceResult(
                usage_record=usage_record,
                usage_cost=usage_cost,
            )

        except Exception:
            session.rollback()
            raise
