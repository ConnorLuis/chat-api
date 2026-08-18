from __future__ import annotations

from sqlalchemy.orm import Session

from src.app.cost import CostSnapshot
from src.app.db.models import UsageCost


class UsageCostRepository:
    """UsageCost query/flush 边界，不负责 commit."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def create(
        self,
        *,
        request_id: str,
        snapshot: CostSnapshot,
    ) -> UsageCost:
        record = UsageCost(
            request_id=request_id,
            pricing_key=(
                snapshot.pricing_key
            ),
            matched_pricing_key=(
                snapshot.matched_pricing_key
            ),
            pricing_version=(
                snapshot.pricing_version
            ),
            currency=snapshot.currency,
            unit_tokens=(
                snapshot.unit_tokens
            ),
            cost_status=(
                snapshot.cost_status
            ),
            prompt_price_per_unit=(
                snapshot
                .prompt_price_per_unit
            ),
            completion_price_per_unit=(
                snapshot
                .completion_price_per_unit
            ),
            prompt_cost=(
                snapshot.prompt_cost
            ),
            completion_cost=(
                snapshot.completion_cost
            ),
            estimated_cost=(
                snapshot.estimated_cost
            ),
        )

        self.session.add(record)
        self.session.flush()

        return record

    def get(
        self,
        request_id: str,
    ) -> UsageCost | None:
        return self.session.get(
            UsageCost,
            request_id,
        )
