from __future__ import annotations

from sqlalchemy.orm import Session

from src.app.cost import (
    PricingCatalog,
    estimate_usage_cost,
    get_pricing_catalog,
)
from src.app.db.models import (
    UsageCost,
    UsageRecord,
)
from src.app.db.repositories import (
    UsageCostRepository,
)


class UsageCostService:
    """UsageRecord 对应的价格与成本快照边界."""

    def __init__(
        self,
        session: Session,
        *,
        catalog: PricingCatalog | None = None,
    ) -> None:
        self.session = session
        self.costs = UsageCostRepository(
            session
        )
        self.catalog = (
            catalog
            or get_pricing_catalog()
        )

    def estimate_for_usage(
        self,
        usage: UsageRecord,
    ):
        return estimate_usage_cost(
            provider=usage.provider,
            model=usage.model,
            prompt_tokens=(
                usage.prompt_tokens
            ),
            completion_tokens=(
                usage.completion_tokens
            ),
            catalog=self.catalog,
        )

    def record_cost_for_usage(
        self,
        usage: UsageRecord,
        *,
        commit: bool = True,
    ) -> UsageCost:
        snapshot = self.estimate_for_usage(
            usage
        )

        try:
            cost = self.costs.create(
                request_id=usage.request_id,
                snapshot=snapshot,
            )

            if commit:
                self.session.commit()
                self.session.refresh(cost)

            else:
                self.session.flush()

            return cost

        except Exception:
            self.session.rollback()
            raise

    def get_cost(
        self,
        request_id: str,
    ) -> UsageCost | None:
        return self.costs.get(
            request_id
        )
