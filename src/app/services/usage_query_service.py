from __future__ import annotations

from collections import defaultdict
from datetime import (
    datetime,
    timezone,
)
from decimal import Decimal

from sqlalchemy.orm import Session

from src.app.cost import COST_QUANTUM
from src.app.db.repositories import (
    UsageGroupBy,
    UsageReportFilters,
    UsageReportRepository,
)


def decimal_to_string(
    value,
) -> str | None:
    if value is None:
        return None

    return format(
        Decimal(value),
        "f",
    )


def decimal_cost_to_string(
    value,
) -> str | None:
    """成本金额统一输出固定 12 位小数."""

    if value is None:
        return None

    normalized = Decimal(
        value
    ).quantize(
        COST_QUANTUM
    )

    return format(
        normalized,
        "f",
    )


def datetime_to_utc(
    value: datetime,
) -> datetime:
    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


class UsageQueryService:
    """UsageRecord / UsageCost 只读查询与聚合服务."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session
        self.reports = UsageReportRepository(
            session
        )

    @staticmethod
    def _cost_payload(
        cost,
    ) -> dict | None:
        if cost is None:
            return None

        return {
            "pricing_key": (
                cost.pricing_key
            ),
            "matched_pricing_key": (
                cost.matched_pricing_key
            ),
            "pricing_version": (
                cost.pricing_version
            ),
            "currency": cost.currency,
            "unit_tokens": (
                cost.unit_tokens
            ),
            "cost_status": (
                cost.cost_status
            ),
            "prompt_price_per_unit": (
                decimal_to_string(
                    cost
                    .prompt_price_per_unit
                )
            ),
            "completion_price_per_unit": (
                decimal_to_string(
                    cost
                    .completion_price_per_unit
                )
            ),
            "prompt_cost": (
                decimal_to_string(
                    cost.prompt_cost
                )
            ),
            "completion_cost": (
                decimal_to_string(
                    cost.completion_cost
                )
            ),
            "estimated_cost": (
                decimal_to_string(
                    cost.estimated_cost
                )
            ),
        }

    @classmethod
    def _record_payload(
        cls,
        usage,
        cost,
    ) -> dict:
        return {
            "request_id": usage.request_id,
            "trace_id": usage.trace_id,
            "conversation_id": (
                usage.conversation_id
            ),
            "request_kind": (
                usage.request_kind
            ),
            "provider": usage.provider,
            "model": usage.model,
            "status": usage.status,
            "usage_source": (
                usage.usage_source
            ),
            "prompt_tokens": (
                usage.prompt_tokens
            ),
            "completion_tokens": (
                usage.completion_tokens
            ),
            "total_tokens": (
                usage.total_tokens
            ),
            "latency_ms": (
                usage.latency_ms
            ),
            "error_type": usage.error_type,
            "created_at": (
                datetime_to_utc(
                    usage.created_at
                )
            ),
            "cost": cls._cost_payload(
                cost
            ),
        }

    def list_records(
        self,
        filters: UsageReportFilters,
        *,
        limit: int,
        offset: int,
    ) -> dict:
        total = self.reports.count_records(
            filters
        )

        rows = self.reports.list_records(
            filters,
            limit=limit,
            offset=offset,
        )

        items = [
            self._record_payload(
                usage,
                cost,
            )
            for usage, cost in rows
        ]

        return {
            "items": items,
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "returned": len(items),
                "has_more": (
                    offset + len(items)
                    < total
                ),
            },
        }

    @staticmethod
    def _new_bucket() -> dict:
        return {
            "request_count": 0,

            "statuses": {
                "succeeded": 0,
                "provider_failed": 0,
                "client_disconnected": 0,
                "persistence_failed": 0,
            },

            "usage_sources": {
                "provider_native": 0,
                "local_estimate": 0,
                "unavailable": 0,
            },

            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,

            "total_latency_ms": 0,

            "cost_statuses": {
                "estimated": 0,
                "unknown_price": 0,
                "usage_unavailable": 0,
                "missing_snapshot": 0,
            },

            "_costs_by_currency": (
                defaultdict(Decimal)
            ),
        }

    @staticmethod
    def _group_key(
        row,
        *,
        group_by: UsageGroupBy,
    ):
        if group_by == "summary":
            return "summary"

        if group_by == "day":
            value = row.group_day

            if hasattr(
                value,
                "isoformat",
            ):
                return value.isoformat()

            return str(value)

        if group_by == "provider":
            return row.group_provider

        if group_by == "model":
            return (
                row.group_provider,
                row.group_model,
            )

        raise ValueError(
            "Unsupported group_by: "
            f"{group_by}"
        )

    @staticmethod
    def _merge_row(
        bucket: dict,
        row,
    ) -> None:
        request_count = int(
            row.request_count or 0
        )

        bucket[
            "request_count"
        ] += request_count

        bucket["statuses"][
            "succeeded"
        ] += int(
            row.succeeded_count or 0
        )

        bucket["statuses"][
            "provider_failed"
        ] += int(
            row.provider_failed_count or 0
        )

        bucket["statuses"][
            "client_disconnected"
        ] += int(
            row.client_disconnected_count
            or 0
        )

        bucket["statuses"][
            "persistence_failed"
        ] += int(
            row.persistence_failed_count
            or 0
        )

        bucket["usage_sources"][
            "provider_native"
        ] += int(
            row.provider_native_count
            or 0
        )

        bucket["usage_sources"][
            "local_estimate"
        ] += int(
            row.local_estimate_count
            or 0
        )

        bucket["usage_sources"][
            "unavailable"
        ] += int(
            row.usage_unavailable_count
            or 0
        )

        bucket["prompt_tokens"] += int(
            row.prompt_tokens or 0
        )

        bucket[
            "completion_tokens"
        ] += int(
            row.completion_tokens or 0
        )

        bucket["total_tokens"] += int(
            row.total_tokens or 0
        )

        bucket[
            "total_latency_ms"
        ] += int(
            row.total_latency_ms or 0
        )

        bucket["cost_statuses"][
            "estimated"
        ] += int(
            row.cost_estimated_count
            or 0
        )

        bucket["cost_statuses"][
            "unknown_price"
        ] += int(
            row.unknown_price_count
            or 0
        )

        bucket["cost_statuses"][
            "usage_unavailable"
        ] += int(
            row
            .cost_usage_unavailable_count
            or 0
        )

        bucket["cost_statuses"][
            "missing_snapshot"
        ] += int(
            row.missing_snapshot_count
            or 0
        )

        if (
            row.cost_currency
            and int(
                row.cost_estimated_count
                or 0
            ) > 0
        ):
            bucket[
                "_costs_by_currency"
            ][row.cost_currency] += (
                Decimal(
                    row.estimated_cost
                    or 0
                )
            )

    @staticmethod
    def _finalize_bucket(
        bucket: dict,
    ) -> dict:
        request_count = bucket[
            "request_count"
        ]

        average_latency = (
            round(
                bucket[
                    "total_latency_ms"
                ]
                / request_count,
                3,
            )
            if request_count
            else 0.0
        )

        costs_by_currency = [
            {
                "currency": currency,
                "estimated_cost": (
                    decimal_cost_to_string(
                        amount
                    )
                ),
            }
            for currency, amount
            in sorted(
                bucket[
                    "_costs_by_currency"
                ].items()
            )
        ]

        return {
            "request_count": (
                request_count
            ),
            "statuses": (
                bucket["statuses"]
            ),
            "usage_sources": (
                bucket["usage_sources"]
            ),
            "prompt_tokens": (
                bucket["prompt_tokens"]
            ),
            "completion_tokens": (
                bucket[
                    "completion_tokens"
                ]
            ),
            "total_tokens": (
                bucket["total_tokens"]
            ),
            "total_latency_ms": (
                bucket[
                    "total_latency_ms"
                ]
            ),
            "average_latency_ms": (
                average_latency
            ),
            "cost_statuses": (
                bucket["cost_statuses"]
            ),
            "costs_by_currency": (
                costs_by_currency
            ),
        }

    def aggregate(
        self,
        filters: UsageReportFilters,
        *,
        group_by: UsageGroupBy,
    ) -> dict | list[dict]:
        rows = self.reports.aggregate(
            filters,
            group_by=group_by,
        )

        buckets: dict = {}

        for row in rows:
            key = self._group_key(
                row,
                group_by=group_by,
            )

            bucket = buckets.setdefault(
                key,
                self._new_bucket(),
            )

            self._merge_row(
                bucket,
                row,
            )

        if group_by == "summary":
            bucket = buckets.get(
                "summary",
                self._new_bucket(),
            )

            return self._finalize_bucket(
                bucket
            )

        items = []

        for key, bucket in buckets.items():
            item = self._finalize_bucket(
                bucket
            )

            if group_by == "day":
                item["date"] = key

            elif group_by == "provider":
                item["provider"] = key

            elif group_by == "model":
                provider, model = key
                item["provider"] = (
                    provider
                )
                item["model"] = model

            items.append(item)

        if group_by == "day":
            items.sort(
                key=lambda item: item[
                    "date"
                ]
            )

        elif group_by == "provider":
            items.sort(
                key=lambda item: (
                    -item["request_count"],
                    item["provider"],
                )
            )

        elif group_by == "model":
            items.sort(
                key=lambda item: (
                    -item["request_count"],
                    item["provider"],
                    item["model"],
                )
            )

        return items

    def grouped_page(
        self,
        filters: UsageReportFilters,
        *,
        group_by: UsageGroupBy,
        limit: int,
        offset: int,
    ) -> dict:
        items = self.aggregate(
            filters,
            group_by=group_by,
        )

        total = len(items)

        selected = items[
            offset:offset + limit
        ]

        return {
            "items": selected,
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "returned": len(
                    selected
                ),
                "has_more": (
                    offset + len(selected)
                    < total
                ),
            },
        }
