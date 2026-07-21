import logging
import time
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.db.session import SessionLocal
from app.models.ai_usage_log import AIUsageLog
from app.repositories.ai_usage_log import AIUsageLogRepository

logger = logging.getLogger(__name__)

# USD per 1,000 input/output tokens. Keep this intentionally small and update
# when provider pricing changes. Unknown model versions are stored with null
# cost rather than guessed. Groq/Ollama are recorded as zero where no direct
# per-token application cost applies.
MODEL_PRICING_PER_1K: dict[tuple[str, str], tuple[Decimal, Decimal] | Decimal] = {
    ("openai", "gpt-4o"): (Decimal("0.0025"), Decimal("0.0100")),
    ("openai", "gpt-4o-mini"): (Decimal("0.00015"), Decimal("0.00060")),
    ("anthropic", "claude-3-5-sonnet-latest"): (
        Decimal("0.0030"),
        Decimal("0.0150"),
    ),
    ("anthropic", "claude-3-5-haiku-latest"): (
        Decimal("0.0008"),
        Decimal("0.0040"),
    ),
    ("gemini", "gemini-2.5-flash"): (
        Decimal("0.00015"),
        Decimal("0.00060"),
    ),
    ("groq", "*"): Decimal("0"),
    ("ollama", "*"): Decimal("0"),
}


def _estimate_cost(
    provider: str,
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> Decimal | None:
    price = MODEL_PRICING_PER_1K.get((provider, model))
    if price is None:
        price = MODEL_PRICING_PER_1K.get((provider, "*"))
    if price is None:
        return None
    if isinstance(price, Decimal):
        return price
    if prompt_tokens is None and completion_tokens is None:
        return None
    input_price, output_price = price
    amount = (
        Decimal(prompt_tokens or 0) * input_price
        + Decimal(completion_tokens or 0) * output_price
    ) / Decimal(1000)
    return amount.quantize(Decimal("0.000001"))


def log_ai_usage(
    workspace_id: UUID | str,
    generated_post_id: UUID | str | None,
    agent_purpose: str,
    provider: str,
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    latency_ms: int | None,
) -> None:
    """Best-effort usage logging; analytics failure never breaks an LLM call."""
    total_tokens = None
    if prompt_tokens is not None or completion_tokens is not None:
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)

    try:
        with SessionLocal() as db:
            row = AIUsageLog(
                workspace_id=UUID(str(workspace_id)),
                generated_post_id=(
                    UUID(str(generated_post_id)) if generated_post_id else None
                ),
                agent_purpose=agent_purpose,
                provider=provider,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=_estimate_cost(
                    provider,
                    model,
                    prompt_tokens,
                    completion_tokens,
                ),
                latency_ms=latency_ms,
            )
            AIUsageLogRepository(db).add(row)
            db.commit()
    except Exception:
        logger.exception(
            "Failed to store AI usage workspace=%s purpose=%s",
            workspace_id,
            agent_purpose,
        )


def _model_identity(model: Any) -> tuple[str, str]:
    class_name = model.__class__.__name__.lower()
    if "openai" in class_name:
        provider = "openai"
    elif "anthropic" in class_name:
        provider = "anthropic"
    elif "google" in class_name or "gemini" in class_name:
        provider = "gemini"
    elif "groq" in class_name:
        provider = "groq"
    elif "ollama" in class_name:
        provider = "ollama"
    else:
        provider = "unknown"

    model_name = (
        getattr(model, "model_name", None)
        or getattr(model, "model", None)
        or getattr(model, "model_id", None)
        or "unknown"
    )
    return provider, str(model_name)


def _usage_from_raw(raw: Any) -> tuple[int | None, int | None]:
    usage = getattr(raw, "usage_metadata", None) or {}
    response_metadata = getattr(raw, "response_metadata", None) or {}
    provider_usage = (
        response_metadata.get("token_usage")
        or response_metadata.get("usage")
        or {}
    )
    prompt_tokens = (
        usage.get("input_tokens")
        or usage.get("prompt_tokens")
        or provider_usage.get("prompt_tokens")
        or provider_usage.get("input_tokens")
    )
    completion_tokens = (
        usage.get("output_tokens")
        or usage.get("completion_tokens")
        or provider_usage.get("completion_tokens")
        or provider_usage.get("output_tokens")
    )
    return (
        int(prompt_tokens) if prompt_tokens is not None else None,
        int(completion_tokens) if completion_tokens is not None else None,
    )


def invoke_structured_with_usage(
    *,
    model: Any,
    schema: Any,
    prompt: Any,
    workspace_id: UUID | str,
    generated_post_id: UUID | str | None,
    agent_purpose: str,
) -> Any:
    """Invoke structured output while retaining the raw message token metadata."""
    started = time.perf_counter()
    raw = None
    call_completed = False
    try:
        try:
            structured = model.with_structured_output(schema, include_raw=True)
        except TypeError:
            # Compatibility for test doubles and adapters that do not expose
            # LangChain's include_raw option; token fields remain null.
            structured = model.with_structured_output(schema)
        response = structured.invoke(prompt)
        call_completed = True
        if isinstance(response, dict):
            raw = response.get("raw")
            parsed = response.get("parsed")
            if parsed is None:
                parsing_error = response.get("parsing_error")
                raise ValueError(f"Structured response parsing failed: {parsing_error}")
        else:
            parsed = response
        return parsed
    finally:
        if call_completed:
            latency_ms = round((time.perf_counter() - started) * 1000)
            provider, model_name = _model_identity(model)
            prompt_tokens, completion_tokens = _usage_from_raw(raw)
            log_ai_usage(
                workspace_id=workspace_id,
                generated_post_id=generated_post_id,
                agent_purpose=agent_purpose,
                provider=provider,
                model=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
            )
