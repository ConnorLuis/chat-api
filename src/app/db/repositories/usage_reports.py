from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import (
    case,
    func,
    select,
)
from sqlalchemy.orm import Session

from src.app.db.models import (
    UsageCost,
    UsageRecord,
)


UsageGroupBy = Literal[
    "summary",
    "day",
    "provider",
    "model",
]


@dataclass(
    frozen=True,
    slots=True,
)
class UsageReportFilters:
    start_time: datetime | None = None
    end_time: datetime | None = None

    status: str | None = None
    usage_source: str | None = None
    cost_status: str | None = None

    provider: str | None = None
    model: str | None = None

    conversation_id: str | None = None
    request_kind: str | None = None


class UsageReportRepository:
    """Usage / cost 查询与聚合 SQL 边界."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    @staticmethod
    def _conditions(
        filters: UsageReportFilters,
    ) -> list:
        conditions = []

        if filters.start_time is not None:
            conditions.append(
                UsageRecord.created_at
                >= filters.start_time
            )

        if filters.end_time is not None:
            # end_time 使用 exclusive 语义。
            conditions.append(
                UsageRecord.created_at
                < filters.end_time
            )

        if filters.status is not None:
            conditions.append(
                UsageRecord.status
                == filters.status
            )

        if (
            filters.usage_source
            is not None
        ):
            conditions.append(
                UsageRecord.usage_source
                == filters.usage_source
            )

        if filters.cost_status is not None:
            if (
                filters.cost_status
                == "missing_snapshot"
            ):
                conditions.append(
                    UsageCost.request_id.is_(
                        None
                    )
                )
            else:
                conditions.append(
                    UsageCost.cost_status
                    == filters.cost_status
                )

        if filters.provider is not None:
            conditions.append(
                UsageRecord.provider
                == filters.provider
            )

        if filters.model is not None:
            conditions.append(
                UsageRecord.model
                == filters.model
            )

        if (
            filters.conversation_id
            is not None
        ):
            conditions.append(
                UsageRecord.conversation_id
                == filters.conversation_id
            )

        if (
            filters.request_kind
            is not None
        ):
            conditions.append(
                UsageRecord.request_kind
                == filters.request_kind
            )

        return conditions

    @staticmethod
    def _joined_statement():
        return (
            select(
                UsageRecord,
                UsageCost,
            )
            .select_from(UsageRecord)
            .outerjoin(
                UsageCost,
                UsageCost.request_id
                == UsageRecord.request_id,
            )
        )

    def count_records(
        self,
        filters: UsageReportFilters,
    ) -> int:
        statement = (
            select(
                func.count(
                    UsageRecord.request_id
                )
            )
            .select_from(UsageRecord)
            .outerjoin(
                UsageCost,
                UsageCost.request_id
                == UsageRecord.request_id,
            )
        )

        conditions = self._conditions(
            filters
        )

        if conditions:
            statement = statement.where(
                *conditions
            )

        return int(
            self.session.scalar(
                statement
            )
            or 0
        )

    def list_records(
        self,
        filters: UsageReportFilters,
        *,
        limit: int,
        offset: int,
    ):
        statement = (
            self._joined_statement()
            .order_by(
                UsageRecord.created_at.desc(),
                UsageRecord.request_id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        conditions = self._conditions(
            filters
        )

        if conditions:
            statement = statement.where(
                *conditions
            )

        return list(
            self.session.execute(
                statement
            ).all()
        )

    def aggregate(
        self,
        filters: UsageReportFilters,
        *,
        group_by: UsageGroupBy,
    ):
        group_expressions = []
        selected_group_columns = []

        if group_by == "day":
            day_expression = func.date(
                UsageRecord.created_at
            ).label("group_day")

            group_expressions.append(
                day_expression
            )
            selected_group_columns.append(
                day_expression
            )

        elif group_by == "provider":
            provider_expression = (
                UsageRecord.provider.label(
                    "group_provider"
                )
            )

            group_expressions.append(
                UsageRecord.provider
            )
            selected_group_columns.append(
                provider_expression
            )

        elif group_by == "model":
            provider_expression = (
                UsageRecord.provider.label(
                    "group_provider"
                )
            )
            model_expression = (
                UsageRecord.model.label(
                    "group_model"
                )
            )

            group_expressions.extend([
                UsageRecord.provider,
                UsageRecord.model,
            ])
            selected_group_columns.extend([
                provider_expression,
                model_expression,
            ])

        elif group_by != "summary":
            raise ValueError(
                "Unsupported usage group: "
                f"{group_by}"
            )

        cost_currency = (
            UsageCost.currency.label(
                "cost_currency"
            )
        )

        statement = (
            select(
                *selected_group_columns,
                cost_currency,

                func.count(
                    UsageRecord.request_id
                ).label("request_count"),

                func.sum(
                    case(
                        (
                            UsageRecord.status
                            == "succeeded",
                            1,
                        ),
                        else_=0,
                    )
                ).label("succeeded_count"),

                func.sum(
                    case(
                        (
                            UsageRecord.status
                            == "provider_failed",
                            1,
                        ),
                        else_=0,
                    )
                ).label(
                    "provider_failed_count"
                ),

                func.sum(
                    case(
                        (
                            UsageRecord.status
                            == "client_disconnected",
                            1,
                        ),
                        else_=0,
                    )
                ).label(
                    "client_disconnected_count"
                ),

                func.sum(
                    case(
                        (
                            UsageRecord.status
                            == "persistence_failed",
                            1,
                        ),
                        else_=0,
                    )
                ).label(
                    "persistence_failed_count"
                ),

                func.sum(
                    case(
                        (
                            UsageRecord.usage_source
                            == "provider_native",
                            1,
                        ),
                        else_=0,
                    )
                ).label(
                    "provider_native_count"
                ),

                func.sum(
                    case(
                        (
                            UsageRecord.usage_source
                            == "local_estimate",
                            1,
                        ),
                        else_=0,
                    )
                ).label(
                    "local_estimate_count"
                ),

                func.sum(
                    case(
                        (
                            UsageRecord.usage_source
                            == "unavailable",
                            1,
                        ),
                        else_=0,
                    )
                ).label(
                    "usage_unavailable_count"
                ),

                func.coalesce(
                    func.sum(
                        UsageRecord.prompt_tokens
                    ),
                    0,
                ).label("prompt_tokens"),

                func.coalesce(
                    func.sum(
                        UsageRecord
                        .completion_tokens
                    ),
                    0,
                ).label(
                    "completion_tokens"
                ),

                func.coalesce(
                    func.sum(
                        UsageRecord.total_tokens
                    ),
                    0,
                ).label("total_tokens"),

                func.coalesce(
                    func.sum(
                        UsageRecord.latency_ms
                    ),
                    0,
                ).label(
                    "total_latency_ms"
                ),

                func.sum(
                    case(
                        (
                            UsageCost.cost_status
                            == "estimated",
                            1,
                        ),
                        else_=0,
                    )
                ).label(
                    "cost_estimated_count"
                ),

                func.sum(
                    case(
                        (
                            UsageCost.cost_status
                            == "unknown_price",
                            1,
                        ),
                        else_=0,
                    )
                ).label(
                    "unknown_price_count"
                ),

                func.sum(
                    case(
                        (
                            UsageCost.cost_status
                            == "usage_unavailable",
                            1,
                        ),
                        else_=0,
                    )
                ).label(
                    "cost_usage_unavailable_count"
                ),

                func.sum(
                    case(
                        (
                            UsageCost.request_id
                            .is_(None),
                            1,
                        ),
                        else_=0,
                    )
                ).label(
                    "missing_snapshot_count"
                ),

                func.coalesce(
                    func.sum(
                        case(
                            (
                                UsageCost.cost_status
                                == "estimated",
                                UsageCost
                                .estimated_cost,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label(
                    "estimated_cost"
                ),
            )
            .select_from(UsageRecord)
            .outerjoin(
                UsageCost,
                UsageCost.request_id
                == UsageRecord.request_id,
            )
        )

        conditions = self._conditions(
            filters
        )

        if conditions:
            statement = statement.where(
                *conditions
            )

        statement = statement.group_by(
            *group_expressions,
            UsageCost.currency,
        )

        return list(
            self.session.execute(
                statement
            ).all()
        )
