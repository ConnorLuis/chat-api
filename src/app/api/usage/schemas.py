from __future__ import annotations

from datetime import (
    date,
    datetime,
)
from typing import Literal

from pydantic import BaseModel


UsageStatus = Literal[
    "succeeded",
    "provider_failed",
    "client_disconnected",
    "persistence_failed",
]

UsageSource = Literal[
    "provider_native",
    "local_estimate",
    "unavailable",
]

StoredCostStatus = Literal[
    "estimated",
    "unknown_price",
    "usage_unavailable",
]

CostStatusFilter = Literal[
    "estimated",
    "unknown_price",
    "usage_unavailable",
    "missing_snapshot",
]

RequestKind = Literal[
    "chat_sync",
    "chat_stream",
]


class PaginationResponse(BaseModel):
    total: int
    limit: int
    offset: int
    returned: int
    has_more: bool


class UsageCostResponse(BaseModel):
    pricing_key: str
    matched_pricing_key: str | None
    pricing_version: str
    currency: str
    unit_tokens: int

    cost_status: StoredCostStatus

    prompt_price_per_unit: str | None
    completion_price_per_unit: str | None

    prompt_cost: str | None
    completion_cost: str | None
    estimated_cost: str | None


class UsageRecordResponse(BaseModel):
    request_id: str
    trace_id: str
    conversation_id: str | None
    request_kind: str

    provider: str
    model: str

    status: UsageStatus
    usage_source: UsageSource

    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None

    latency_ms: int
    error_type: str | None
    created_at: datetime

    # 旧 Day7 数据可能没有成本快照；
    # 不在读取时按当前价格重新估价。
    cost: UsageCostResponse | None


class UsageRecordListResponse(BaseModel):
    items: list[UsageRecordResponse]
    pagination: PaginationResponse


class UsageStatusCounts(BaseModel):
    succeeded: int
    provider_failed: int
    client_disconnected: int
    persistence_failed: int


class UsageSourceCounts(BaseModel):
    provider_native: int
    local_estimate: int
    unavailable: int


class UsageCostStatusCounts(BaseModel):
    estimated: int
    unknown_price: int
    usage_unavailable: int
    missing_snapshot: int


class CurrencyCostResponse(BaseModel):
    currency: str
    estimated_cost: str


class UsageAggregateMetrics(BaseModel):
    request_count: int

    statuses: UsageStatusCounts
    usage_sources: UsageSourceCounts

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    total_latency_ms: int
    average_latency_ms: float

    cost_statuses: UsageCostStatusCounts

    # 不跨币种直接求和。
    costs_by_currency: list[
        CurrencyCostResponse
    ]


class UsageSummaryResponse(
    UsageAggregateMetrics
):
    pass


class UsageDailyItem(
    UsageAggregateMetrics
):
    date: date


class UsageDailyResponse(BaseModel):
    items: list[UsageDailyItem]
    pagination: PaginationResponse


class UsageProviderItem(
    UsageAggregateMetrics
):
    provider: str


class UsageProviderResponse(BaseModel):
    items: list[UsageProviderItem]
    pagination: PaginationResponse


class UsageModelItem(
    UsageAggregateMetrics
):
    provider: str
    model: str


class UsageModelResponse(BaseModel):
    items: list[UsageModelItem]
    pagination: PaginationResponse


class PricingRateResponse(BaseModel):
    pricing_key: str
    provider: str
    model: str

    prompt_price_per_unit: str
    completion_price_per_unit: str


class PricingCatalogResponse(BaseModel):
    version: str
    currency: str
    unit_tokens: int
    prices: list[PricingRateResponse]
