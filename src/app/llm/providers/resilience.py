from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, replace

from .base import ChatProvider
from .errors import (
    ChatProviderError,
    ProviderStreamInterruptedError,
    normalize_provider_error,
)
from .schemas import (
    ProviderAttempt,
    ProviderChatChunk,
    ProviderChatRequest,
    ProviderChatResponse,
    ProviderExecutionMetadata,
)


@dataclass(frozen=True, slots=True)
class ProviderRetryPolicy:
    """Provider retry policy; max_attempts includes the initial call."""

    max_attempts: int = 2
    base_delay_ms: int = 100
    max_delay_ms: int = 1_000

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay_ms < 0:
            raise ValueError("base_delay_ms must be non-negative")
        if self.max_delay_ms < self.base_delay_ms:
            raise ValueError(
                "max_delay_ms must be greater than or equal to "
                "base_delay_ms"
            )

    def delay_seconds(self, failed_attempt: int) -> float:
        delay_ms = min(
            self.base_delay_ms * (2 ** (failed_attempt - 1)),
            self.max_delay_ms,
        )
        return delay_ms / 1_000


class ResilientChatProvider:
    """Transparent retry/fallback decorator for a ChatProvider."""

    def __init__(
        self,
        *,
        primary: ChatProvider,
        retry_policy: ProviderRetryPolicy | None = None,
        fallback: ChatProvider | None = None,
        fallback_model: str | None = None,
        sync_sleep: Callable[[float], None] = time.sleep,
        async_sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if fallback is not None and fallback.name == primary.name:
            raise ValueError("fallback provider must differ from primary")

        self.primary = primary
        self.fallback = fallback
        self.fallback_model = (
            fallback_model.strip()
            if fallback_model and fallback_model.strip()
            else None
        )
        self.retry_policy = retry_policy or ProviderRetryPolicy()
        self._sync_sleep = sync_sleep
        self._async_sleep = async_sleep

    @property
    def name(self) -> str:
        return self.primary.name

    @property
    def default_model(self) -> str | None:
        return getattr(self.primary, "default_model", None)

    def resolve_model(self, requested_model: str | None = None) -> str:
        return self.primary.resolve_model(requested_model)

    @staticmethod
    def _resolved_model(
        provider: ChatProvider,
        request: ProviderChatRequest,
    ) -> str:
        try:
            model = provider.resolve_model(request.model)
        except Exception:
            model = request.model or getattr(
                provider,
                "default_model",
                None,
            )
        return model or "unknown"

    def _candidates(
        self,
        request: ProviderChatRequest,
    ) -> tuple[tuple[ChatProvider, ProviderChatRequest, bool], ...]:
        candidates = [(self.primary, request, False)]

        if self.fallback is not None:
            candidates.append(
                (
                    self.fallback,
                    replace(
                        request,
                        model=self.fallback_model,
                    ),
                    True,
                )
            )

        return tuple(candidates)

    def _execution(
        self,
        *,
        final_provider: str,
        attempts: list[ProviderAttempt],
        retries: int,
        fallback_used: bool,
    ) -> ProviderExecutionMetadata:
        return ProviderExecutionMetadata(
            primary_provider=self.primary.name,
            final_provider=final_provider,
            attempts=tuple(attempts),
            retries=retries,
            fallback_used=fallback_used,
        )

    @staticmethod
    def _latency_ms(started_at: float) -> int:
        return int((time.perf_counter() - started_at) * 1_000)

    def chat(
        self,
        request: ProviderChatRequest,
    ) -> ProviderChatResponse:
        attempts: list[ProviderAttempt] = []
        retries = 0

        for provider, candidate_request, fallback_used in self._candidates(request):
            model = self._resolved_model(provider, candidate_request)

            for provider_attempt in range(1, self.retry_policy.max_attempts + 1):
                started_at = time.perf_counter()

                try:
                    response = provider.chat(candidate_request)
                except Exception as raw_error:
                    error = normalize_provider_error(provider.name, raw_error)
                    attempts.append(
                        ProviderAttempt(
                            ordinal=len(attempts) + 1,
                            provider=provider.name,
                            model=model,
                            outcome="failed",
                            latency_ms=self._latency_ms(started_at),
                            error_code=error.code,
                            retryable=error.retryable,
                        )
                    )

                    if (
                        error.retryable
                        and provider_attempt < self.retry_policy.max_attempts
                    ):
                        retries += 1
                        self._sync_sleep(
                            self.retry_policy.delay_seconds(provider_attempt)
                        )
                        continue

                    if (
                        error.retryable
                        and not fallback_used
                        and self.fallback is not None
                    ):
                        break

                    error.execution = self._execution(
                        final_provider=provider.name,
                        attempts=attempts,
                        retries=retries,
                        fallback_used=fallback_used,
                    )

                    if error is raw_error:
                        raise
                    raise error from raw_error

                attempts.append(
                    ProviderAttempt(
                        ordinal=len(attempts) + 1,
                        provider=provider.name,
                        model=response.model or model,
                        outcome="succeeded",
                        latency_ms=self._latency_ms(started_at),
                    )
                )
                final_provider = response.provider or provider.name
                execution = self._execution(
                    final_provider=final_provider,
                    attempts=attempts,
                    retries=retries,
                    fallback_used=fallback_used,
                )
                return replace(
                    response,
                    provider=final_provider,
                    model=response.model or model,
                    execution=execution,
                )

        raise RuntimeError("provider candidate loop ended unexpectedly")

    @staticmethod
    async def _close_iterator(iterator: AsyncIterator[ProviderChatChunk] | None) -> None:
        if iterator is None:
            return
        close = getattr(iterator, "aclose", None)
        if callable(close):
            try:
                await close()
            except (asyncio.CancelledError, GeneratorExit):
                raise
            except Exception:
                pass

    async def stream(
        self,
        request: ProviderChatRequest,
    ) -> AsyncIterator[ProviderChatChunk]:
        attempts: list[ProviderAttempt] = []
        retries = 0

        for provider, candidate_request, fallback_used in self._candidates(request):
            model = self._resolved_model(provider, candidate_request)

            for provider_attempt in range(1, self.retry_policy.max_attempts + 1):
                iterator: AsyncIterator[ProviderChatChunk] | None = None
                buffered: list[ProviderChatChunk] = []
                active_provider = provider.name
                active_model = model
                started_at = time.perf_counter()

                try:
                    iterator = provider.stream(candidate_request).__aiter__()

                    while True:
                        chunk = await anext(iterator)
                        buffered.append(chunk)
                        active_provider = chunk.provider or active_provider
                        active_model = chunk.model or active_model

                        if chunk.delta != "":
                            break

                except StopAsyncIteration:
                    await self._close_iterator(iterator)
                    attempts.append(
                        ProviderAttempt(
                            ordinal=len(attempts) + 1,
                            provider=provider.name,
                            model=active_model,
                            outcome="succeeded",
                            latency_ms=self._latency_ms(started_at),
                        )
                    )
                    execution = self._execution(
                        final_provider=active_provider,
                        attempts=attempts,
                        retries=retries,
                        fallback_used=fallback_used,
                    )

                    if buffered:
                        for index, item in enumerate(buffered):
                            if index == len(buffered) - 1:
                                item = replace(item, execution=execution)
                            yield item
                    else:
                        yield ProviderChatChunk(
                            delta="",
                            provider=active_provider,
                            model=active_model,
                            execution=execution,
                        )
                    return

                except (asyncio.CancelledError, GeneratorExit):
                    await self._close_iterator(iterator)
                    raise

                except Exception as raw_error:
                    await self._close_iterator(iterator)
                    error = normalize_provider_error(provider.name, raw_error)
                    attempts.append(
                        ProviderAttempt(
                            ordinal=len(attempts) + 1,
                            provider=provider.name,
                            model=active_model,
                            outcome="failed",
                            latency_ms=self._latency_ms(started_at),
                            error_code=error.code,
                            retryable=error.retryable,
                        )
                    )

                    if (
                        error.retryable
                        and provider_attempt < self.retry_policy.max_attempts
                    ):
                        retries += 1
                        await self._async_sleep(
                            self.retry_policy.delay_seconds(provider_attempt)
                        )
                        continue

                    if (
                        error.retryable
                        and not fallback_used
                        and self.fallback is not None
                    ):
                        break

                    error.execution = self._execution(
                        final_provider=provider.name,
                        attempts=attempts,
                        retries=retries,
                        fallback_used=fallback_used,
                    )
                    if error is raw_error:
                        raise
                    raise error from raw_error

                attempts.append(
                    ProviderAttempt(
                        ordinal=len(attempts) + 1,
                        provider=provider.name,
                        model=active_model,
                        outcome="stream_started",
                        latency_ms=self._latency_ms(started_at),
                    )
                )
                started_execution = self._execution(
                    final_provider=active_provider,
                    attempts=attempts,
                    retries=retries,
                    fallback_used=fallback_used,
                )

                try:
                    for index, item in enumerate(buffered):
                        if index == len(buffered) - 1:
                            item = replace(item, execution=started_execution)
                        yield item

                    assert iterator is not None
                    async for chunk in iterator:
                        active_provider = chunk.provider or active_provider
                        active_model = chunk.model or active_model
                        yield chunk

                except (asyncio.CancelledError, GeneratorExit):
                    raise

                except Exception as raw_error:
                    error = normalize_provider_error(provider.name, raw_error)
                    attempts[-1] = ProviderAttempt(
                        ordinal=attempts[-1].ordinal,
                        provider=provider.name,
                        model=active_model,
                        outcome="stream_interrupted",
                        latency_ms=self._latency_ms(started_at),
                        error_code=error.code,
                        retryable=False,
                    )
                    execution = self._execution(
                        final_provider=active_provider,
                        attempts=attempts,
                        retries=retries,
                        fallback_used=fallback_used,
                    )
                    interrupted = ProviderStreamInterruptedError(
                        (
                            f"{provider.name} provider stream interrupted "
                            f"after output started: {error}"
                        ),
                        provider=provider.name,
                        status_code=error.status_code,
                        execution=execution,
                        cause_code=error.code,
                    )
                    raise interrupted from raw_error

                else:
                    attempts[-1] = ProviderAttempt(
                        ordinal=attempts[-1].ordinal,
                        provider=provider.name,
                        model=active_model,
                        outcome="succeeded",
                        latency_ms=self._latency_ms(started_at),
                    )
                    execution = self._execution(
                        final_provider=active_provider,
                        attempts=attempts,
                        retries=retries,
                        fallback_used=fallback_used,
                    )
                    yield ProviderChatChunk(
                        delta="",
                        provider=active_provider,
                        model=active_model,
                        execution=execution,
                    )
                    return

                finally:
                    await self._close_iterator(iterator)

        raise RuntimeError("provider candidate loop ended unexpectedly")
