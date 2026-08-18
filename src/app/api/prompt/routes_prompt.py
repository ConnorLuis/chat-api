import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Body

from src.app.api.routes_chat import provider_model
from src.app.core.settings import settings
from src.app.core.errors import build_error
from src.app.llm.prompt_registry import PromptRegistry, ensure_system_prompt
from src.app.llm.run_logger import append_jsonl
from src.app.llm.providers import (
    build_provider_request,
    get_chat_provider,
    provider_execution_payload,
    provider_execution_target,
)
from src.app.llm.schemas import PromptCompareResponse, PromptCompareRequest, PromptCompareItem, PromptRef, PromptCompareMetrics

router = APIRouter()
prompt_registry = PromptRegistry(settings.PROMPTS_DIR)

@router.post("/prompt/compare",  response_model=PromptCompareResponse)
def prompt_compare(body: PromptCompareRequest = Body(...)):

    compare_group_id = str(uuid4())
    provider = get_chat_provider(body.provider)

    def run_variant(prompt_ref: PromptRef, variant: str) -> PromptCompareItem:
        trace_id = str(uuid4())

        start = time.perf_counter()
        prompt_id = prompt_ref.prompt_id
        prompt_version = prompt_ref.prompt_version or "v1"
        prompt_vars = prompt_ref.prompt_vars

        messages = body.messages
        system_text = None
        if prompt_id:
            template = prompt_registry.get(prompt_id, prompt_version)
            system_text = prompt_registry.render(template, prompt_vars)
            messages = ensure_system_prompt(messages, system_text)

        active_provider = provider.name
        active_model = provider_model(provider, body.model)
        execution_payload = None

        provider_request = build_provider_request(
            messages,
            model=body.model,
            temperature=body.temperature,
            top_p=body.top_p,
            max_tokens=body.max_tokens,
        )

        try:
            provider_response = provider.chat(provider_request)
            answer = provider_response.content

            active_provider = (
                provider_response.provider
                or active_provider
            )
            active_model = (
                provider_response.model
                or active_model
            )
            execution_payload = (
                provider_execution_payload(
                    provider_response.execution
                )
            )
        except Exception as e:
            execution = getattr(
                e,
                "execution",
                None,
            )
            active_provider, active_model = (
                provider_execution_target(
                    execution,
                    provider=active_provider,
                    model=active_model,
                )
            )
            execution_payload = (
                provider_execution_payload(
                    execution
                )
            )
            latency_ms = int((time.perf_counter() - start) * 1000)
            err = build_error(
                trace_id,
                active_provider,
                active_model,
                latency_ms,
                f"{active_provider} failed: {str(e)}",
                provider_execution=(
                    execution_payload
                ),
            )
            record = {
                "compare_group_id": compare_group_id,
                "variant": variant,
                "trace_id": trace_id,
                "mode": "compare",
                "provider": active_provider,
                "model": active_model,
                "prompt_id": prompt_id or "none",
                "prompt_version": prompt_version if prompt_id else "none",
                "latency_ms": latency_ms,
                "prompt_chars": len(system_text) if system_text else 0,
                "output_chars": 0,
                "temperature":body.temperature,
                "top_p":body.top_p,
                "max_tokens":body.max_tokens,
                "error": str(e),
                "provider_execution": (
                    execution_payload
                ),
            }
            append_jsonl(settings.RUN_LOG_PATH, record)
            raise HTTPException(status_code=502, detail=err)
        latency_ms = int((time.perf_counter() - start) * 1000)
        metadata = {
            "provider": active_provider,
            "model": active_model,
            "latency_ms": latency_ms,
            "prompt_id": prompt_id,
            "prompt_version": prompt_version if prompt_id else "none",
            "provider_execution": execution_payload,
        }
        # 打印日志：便于后端监控
        record = {
            "compare_group_id": compare_group_id,
            "variant": variant,
            "trace_id": trace_id,
            "mode": "compare",
            "provider": active_provider,
            "model": active_model,
            "prompt_id": prompt_id,
            "prompt_version": prompt_version if prompt_id else "none",
            "latency_ms": latency_ms,
            "prompt_chars": len(system_text) if system_text else 0,
            "output_chars": len(answer),
            "temperature": body.temperature,
            "top_p": body.top_p,
            "max_tokens": body.max_tokens,
            "provider_execution": execution_payload,
        }
        append_jsonl(settings.RUN_LOG_PATH, record)
        return PromptCompareItem(trace_id=trace_id, answer=answer, metadata=metadata)

    a = run_variant(body.prompt_a, "A")
    b = run_variant(body.prompt_b, "B")
    metrics = PromptCompareMetrics(latency_ms_a=a.metadata.latency_ms, latency_ms_b=b.metadata.latency_ms, diff_latency_ms=a.metadata.latency_ms - b.metadata.latency_ms,
                                  output_chars_a=len(a.answer), output_chars_b=len(b.answer), output_chars_diff=len(a.answer) - len(b.answer))
    return PromptCompareResponse(compare_group_id=compare_group_id, a=a, b=b, metrics=metrics)
