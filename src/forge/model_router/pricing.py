"""Versioned text-token estimates. Unknown usage/rates never become zero."""

import hashlib
import json
from copy import deepcopy
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from forge.runtime.models import ModelCall

REVISION = "standard-text-2026-09-18"
# Verified official standard paid text rates, USD per million tokens.
DEFAULT_PRICES = {
    "gemini-3.1-flash-lite": {
        "provider": "google",
        "input": "0.25",
        "cached": "0.025",
        "output": "1.50",
    },
    "gpt-4.1-mini": {"provider": "openai", "input": "0.40", "cached": "0.10", "output": "1.60"},
    "gpt-4.1-mini-2025-04-14": {
        "provider": "openai",
        "input": "0.40",
        "cached": "0.10",
        "output": "1.60",
    },
}


class Price(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(pattern="^(google|openai)$")
    input: Decimal = Field(ge=0, le=10000, allow_inf_nan=False)
    cached: Decimal = Field(ge=0, le=10000, allow_inf_nan=False)
    output: Decimal = Field(ge=0, le=10000, allow_inf_nan=False)


def snapshot(overrides):
    values = deepcopy(DEFAULT_PRICES)
    values.update(
        {
            name: Price.model_validate(value).model_dump(mode="json")
            for name, value in overrides.items()
        }
    )
    digest = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
    return {
        "revision": REVISION,
        "fingerprint": digest,
        "rates": values,
        "basis": "standard-paid-text-estimate",
    }


def count(value):
    if type(value) is not int or value < 0:
        raise ValueError("Invalid token count")
    return value


def estimate(call, catalog):
    if call.status == "SKIPPED":
        return Decimal("0"), {"status": "NOT_SENT"}
    if call.provider == "fake":
        return Decimal("0"), {"status": "SIMULATED"}
    rate = catalog.get("rates", {}).get(call.actual_model)
    if not rate or rate["provider"] != call.provider:
        return None, {"status": "UNKNOWN_PRICE"}
    if call.status != "COMPLETED":
        return None, {"status": "UNKNOWN_USAGE"}
    try:
        inputs, outputs = count(call.input_tokens), count(call.output_tokens)
        usage = call.usage or {}
        if call.provider == "google":
            cached = count(usage.get("cached_content_token_count", 0))
            thinking = count(usage.get("thoughts_token_count", 0))
            outputs += thinking
            if usage.get("tool_use_prompt_token_count", 0):
                return None, {"status": "UNSUPPORTED_USAGE"}
        else:
            if usage.get("service_tier") not in (None, "default"):
                return None, {"status": "UNSUPPORTED_USAGE"}
            details = usage.get("input_tokens_details") or {}
            cached = count(details.get("cached_tokens", 0))
            # Cache-write billing differs by model; do not guess a rate.
            if details.get("cache_write_tokens", 0):
                return None, {"status": "UNSUPPORTED_USAGE"}
        if cached > inputs:
            raise ValueError
        amount = (
            (inputs - cached) * Decimal(rate["input"])
            + cached * Decimal(rate["cached"])
            + outputs * Decimal(rate["output"])
        ) / Decimal(1_000_000)
        return amount.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP), {
            "status": "ESTIMATED",
            "pricing_revision": catalog.get("revision"),
            "rates_per_million_usd": rate,
            "input_tokens": inputs,
            "cached_input_tokens": cached,
            "billable_output_tokens": outputs,
        }
    except (TypeError, ValueError, ArithmeticError, AttributeError):
        return None, {"status": "UNKNOWN_USAGE"}


async def record(session, run, call):
    catalog = run.execution_config.get("pricing_snapshot", {})
    call.estimated_cost, details = estimate(call, catalog)
    call.cost_details = {**(call.cost_details or {}), **details}
    await session.flush()
    calls = list(await session.scalars(select(ModelCall).where(ModelCall.run_id == run.id)))
    known = sum((c.estimated_cost for c in calls if c.estimated_cost is not None), Decimal("0"))
    unknown = sum(c.estimated_cost is None for c in calls)
    run.total_cost = None if unknown else known
    run.execution_config = {
        **run.execution_config,
        "cost_summary": {
            "known_cost_usd": format(known, ".8f"),
            "unknown_calls": unknown,
            "status": "INCOMPLETE" if unknown else "ESTIMATED",
        },
    }


def budget_exceeded(run):
    limit = run.execution_config.get("max_cost_per_run_usd")
    known = run.execution_config.get("cost_summary", {}).get("known_cost_usd", "0")
    return limit is not None and Decimal(known) >= Decimal(limit)
