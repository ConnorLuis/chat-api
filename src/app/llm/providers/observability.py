from __future__ import annotations

from .schemas import ProviderExecutionMetadata


def provider_execution_payload(
    execution: ProviderExecutionMetadata | None,
) -> dict | None:
    """Return the public retry/fallback payload when available."""

    if execution is None:
        return None

    return execution.as_dict()


def provider_execution_target(
    execution: ProviderExecutionMetadata | None,
    *,
    provider: str,
    model: str,
) -> tuple[str, str]:
    """Resolve the final attempted provider/model for accounting."""

    if execution is None:
        return provider, model

    final_provider = (
        execution.final_provider
        or provider
    )
    final_model = model

    if execution.attempts:
        final_model = (
            execution.attempts[-1].model
            or model
        )

    return final_provider, final_model
