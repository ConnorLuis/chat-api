from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from src.app.db.base import Base
from src.app.db.types import UTCDateTime
from src.app.db.utils import utc_now


class UsageCost(Base):
    """一次 UsageRecord 对应的不可变价格与成本快照."""

    __tablename__ = "usage_costs"

    __table_args__ = (
        CheckConstraint(
            (
                "cost_status IN ("
                "'estimated', "
                "'unknown_price', "
                "'usage_unavailable'"
                ")"
            ),
            name="ck_usage_costs_status",
        ),
        CheckConstraint(
            "unit_tokens > 0",
            name="ck_usage_costs_unit_tokens",
        ),
        CheckConstraint(
            (
                "prompt_price_per_unit IS NULL "
                "OR prompt_price_per_unit >= 0"
            ),
            name=(
                "ck_usage_costs_prompt_price"
            ),
        ),
        CheckConstraint(
            (
                "completion_price_per_unit "
                "IS NULL "
                "OR completion_price_per_unit "
                ">= 0"
            ),
            name=(
                "ck_usage_costs_completion_price"
            ),
        ),
        CheckConstraint(
            (
                "prompt_cost IS NULL "
                "OR prompt_cost >= 0"
            ),
            name="ck_usage_costs_prompt_cost",
        ),
        CheckConstraint(
            (
                "completion_cost IS NULL "
                "OR completion_cost >= 0"
            ),
            name=(
                "ck_usage_costs_completion_cost"
            ),
        ),
        CheckConstraint(
            (
                "estimated_cost IS NULL "
                "OR estimated_cost >= 0"
            ),
            name=(
                "ck_usage_costs_estimated_cost"
            ),
        ),
        CheckConstraint(
            (
                "("
                "cost_status = 'estimated' "
                "AND matched_pricing_key "
                "IS NOT NULL "
                "AND prompt_price_per_unit "
                "IS NOT NULL "
                "AND completion_price_per_unit "
                "IS NOT NULL "
                "AND prompt_cost IS NOT NULL "
                "AND completion_cost IS NOT NULL "
                "AND estimated_cost IS NOT NULL"
                ") OR ("
                "cost_status != 'estimated' "
                "AND matched_pricing_key IS NULL "
                "AND prompt_price_per_unit "
                "IS NULL "
                "AND completion_price_per_unit "
                "IS NULL "
                "AND prompt_cost IS NULL "
                "AND completion_cost IS NULL "
                "AND estimated_cost IS NULL"
                ")"
            ),
            name=(
                "ck_usage_costs_status_values"
            ),
        ),
        CheckConstraint(
            (
                "estimated_cost IS NULL "
                "OR prompt_cost IS NULL "
                "OR completion_cost IS NULL "
                "OR estimated_cost = "
                "prompt_cost + completion_cost"
            ),
            name=(
                "ck_usage_costs_total_consistency"
            ),
        ),
        Index(
            "ix_usage_costs_status_created",
            "cost_status",
            "created_at",
        ),
    )

    request_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "usage_records.request_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    # 实际请求的 provider:model。
    pricing_key: Mapped[str] = mapped_column(
        String(260),
        nullable=False,
    )

    # 实际命中的 exact 或 wildcard catalog key。
    matched_pricing_key: Mapped[
        str | None
    ] = mapped_column(
        String(260),
        nullable=True,
    )

    pricing_version: Mapped[str] = (
        mapped_column(
            String(100),
            nullable=False,
        )
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )

    unit_tokens: Mapped[int] = (
        mapped_column(
            Integer,
            nullable=False,
        )
    )

    cost_status: Mapped[str] = (
        mapped_column(
            String(32),
            nullable=False,
        )
    )

    prompt_price_per_unit: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(
            precision=24,
            scale=12,
            asdecimal=True,
        ),
        nullable=True,
    )

    completion_price_per_unit: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(
            precision=24,
            scale=12,
            asdecimal=True,
        ),
        nullable=True,
    )

    prompt_cost: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(
            precision=24,
            scale=12,
            asdecimal=True,
        ),
        nullable=True,
    )

    completion_cost: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(
            precision=24,
            scale=12,
            asdecimal=True,
        ),
        nullable=True,
    )

    estimated_cost: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(
            precision=24,
            scale=12,
            asdecimal=True,
        ),
        nullable=True,
    )

    created_at: Mapped[datetime] = (
        mapped_column(
            UTCDateTime(),
            nullable=False,
            default=utc_now,
        )
    )
