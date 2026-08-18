from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
from typing import Annotated

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from src.app.cost import (
    get_pricing_catalog,
)
from src.app.db.repositories import (
    UsageReportFilters,
)
from src.app.db.session import (
    get_session_factory,
)
from src.app.services import (
    UsageQueryService,
)

from .schemas import (
    CostStatusFilter,
    PricingCatalogResponse,
    RequestKind,
    UsageDailyResponse,
    UsageModelResponse,
    UsageProviderResponse,
    UsageRecordListResponse,
    UsageSource,
    UsageStatus,
    UsageSummaryResponse,
)


router = APIRouter(
    prefix="/usage",
    tags=["usage"],
)


def decimal_string(value) -> str:
    return format(value, "f")


def normalize_datetime(
    value: datetime | None,
    *,
    field_name: str,
) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{field_name} must include "
                "a timezone offset"
            ),
        )

    return value.astimezone(
        timezone.utc
    )


def build_filters(
    *,
    start_time: datetime | None,
    end_time: datetime | None,
    status: str | None,
    usage_source: str | None,
    cost_status: str | None,
    provider: str | None,
    model: str | None,
    conversation_id: str | None,
    request_kind: str | None,
) -> UsageReportFilters:
    normalized_start = normalize_datetime(
        start_time,
        field_name="start_time",
    )
    normalized_end = normalize_datetime(
        end_time,
        field_name="end_time",
    )

    if (
        normalized_start is not None
        and normalized_end is not None
        and normalized_end
        <= normalized_start
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "end_time must be greater "
                "than start_time"
            ),
        )

    normalized_provider = (
        provider.strip().lower()
        if provider
        else None
    )

    normalized_model = (
        model.strip()
        if model
        else None
    )

    return UsageReportFilters(
        start_time=normalized_start,
        end_time=normalized_end,
        status=status,
        usage_source=usage_source,
        cost_status=cost_status,
        provider=normalized_provider,
        model=normalized_model,
        conversation_id=(
            conversation_id
        ),
        request_kind=request_kind,
    )


@router.get(
    "/pricing",
    response_model=PricingCatalogResponse,
)
def get_usage_pricing():
    catalog = get_pricing_catalog()

    prices = [
        {
            "pricing_key": rate.key,
            "provider": rate.provider,
            "model": rate.model,
            "prompt_price_per_unit": (
                decimal_string(
                    rate
                    .prompt_price_per_unit
                )
            ),
            "completion_price_per_unit": (
                decimal_string(
                    rate
                    .completion_price_per_unit
                )
            ),
        }
        for rate in sorted(
            catalog.rates.values(),
            key=lambda item: item.key,
        )
    ]

    return {
        "version": catalog.version,
        "currency": catalog.currency,
        "unit_tokens": (
            catalog.unit_tokens
        ),
        "prices": prices,
    }


def common_filters(
    start_time: datetime | None,
    end_time: datetime | None,
    status: str | None,
    usage_source: str | None,
    cost_status: str | None,
    provider: str | None,
    model: str | None,
    conversation_id: str | None,
    request_kind: str | None,
) -> UsageReportFilters:
    return build_filters(
        start_time=start_time,
        end_time=end_time,
        status=status,
        usage_source=usage_source,
        cost_status=cost_status,
        provider=provider,
        model=model,
        conversation_id=(
            conversation_id
        ),
        request_kind=request_kind,
    )


@router.get(
    "/records",
    response_model=UsageRecordListResponse,
)
def list_usage_records(
    start_time: datetime | None = None,
    end_time: datetime | None = None,

    status: UsageStatus | None = None,
    usage_source: UsageSource | None = None,
    cost_status: CostStatusFilter | None = None,

    provider: str | None = None,
    model: str | None = None,

    conversation_id: str | None = None,
    request_kind: RequestKind | None = None,

    limit: Annotated[
        int,
        Query(ge=1, le=200),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
):
    filters = common_filters(
        start_time,
        end_time,
        status,
        usage_source,
        cost_status,
        provider,
        model,
        conversation_id,
        request_kind,
    )

    with (
        get_session_factory()()
        as session
    ):
        return UsageQueryService(
            session
        ).list_records(
            filters,
            limit=limit,
            offset=offset,
        )


@router.get(
    "/summary",
    response_model=UsageSummaryResponse,
)
def get_usage_summary(
    start_time: datetime | None = None,
    end_time: datetime | None = None,

    status: UsageStatus | None = None,
    usage_source: UsageSource | None = None,
    cost_status: CostStatusFilter | None = None,

    provider: str | None = None,
    model: str | None = None,

    conversation_id: str | None = None,
    request_kind: RequestKind | None = None,
):
    filters = common_filters(
        start_time,
        end_time,
        status,
        usage_source,
        cost_status,
        provider,
        model,
        conversation_id,
        request_kind,
    )

    with (
        get_session_factory()()
        as session
    ):
        return UsageQueryService(
            session
        ).aggregate(
            filters,
            group_by="summary",
        )


@router.get(
    "/daily",
    response_model=UsageDailyResponse,
)
def get_daily_usage(
    start_time: datetime | None = None,
    end_time: datetime | None = None,

    status: UsageStatus | None = None,
    usage_source: UsageSource | None = None,
    cost_status: CostStatusFilter | None = None,

    provider: str | None = None,
    model: str | None = None,

    conversation_id: str | None = None,
    request_kind: RequestKind | None = None,

    limit: Annotated[
        int,
        Query(ge=1, le=366),
    ] = 90,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
):
    filters = common_filters(
        start_time,
        end_time,
        status,
        usage_source,
        cost_status,
        provider,
        model,
        conversation_id,
        request_kind,
    )

    with (
        get_session_factory()()
        as session
    ):
        return UsageQueryService(
            session
        ).grouped_page(
            filters,
            group_by="day",
            limit=limit,
            offset=offset,
        )


@router.get(
    "/providers",
    response_model=UsageProviderResponse,
)
def get_provider_usage(
    start_time: datetime | None = None,
    end_time: datetime | None = None,

    status: UsageStatus | None = None,
    usage_source: UsageSource | None = None,
    cost_status: CostStatusFilter | None = None,

    provider: str | None = None,
    model: str | None = None,

    conversation_id: str | None = None,
    request_kind: RequestKind | None = None,

    limit: Annotated[
        int,
        Query(ge=1, le=200),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
):
    filters = common_filters(
        start_time,
        end_time,
        status,
        usage_source,
        cost_status,
        provider,
        model,
        conversation_id,
        request_kind,
    )

    with (
        get_session_factory()()
        as session
    ):
        return UsageQueryService(
            session
        ).grouped_page(
            filters,
            group_by="provider",
            limit=limit,
            offset=offset,
        )


@router.get(
    "/models",
    response_model=UsageModelResponse,
)
def get_model_usage(
    start_time: datetime | None = None,
    end_time: datetime | None = None,

    status: UsageStatus | None = None,
    usage_source: UsageSource | None = None,
    cost_status: CostStatusFilter | None = None,

    provider: str | None = None,
    model: str | None = None,

    conversation_id: str | None = None,
    request_kind: RequestKind | None = None,

    limit: Annotated[
        int,
        Query(ge=1, le=200),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
):
    filters = common_filters(
        start_time,
        end_time,
        status,
        usage_source,
        cost_status,
        provider,
        model,
        conversation_id,
        request_kind,
    )

    with (
        get_session_factory()()
        as session
    ):
        return UsageQueryService(
            session
        ).grouped_page(
            filters,
            group_by="model",
            limit=limit,
            offset=offset,
        )
