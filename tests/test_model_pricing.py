from decimal import Decimal
from types import SimpleNamespace

import pytest

from forge.model_router.pricing import estimate, snapshot


def call(**changes):
    return SimpleNamespace(
        provider="openai",
        actual_model="gpt-4.1-mini",
        status="COMPLETED",
        input_tokens=1000,
        output_tokens=100,
        usage={},
        **changes,
    )


def test_standard_cached_input_and_reasoning_included_once():
    value = call()
    value.usage = {
        "input_tokens_details": {"cached_tokens": 500},
        "output_tokens_details": {"reasoning_tokens": 50},
    }
    amount, details = estimate(value, snapshot({}))
    assert amount == Decimal("0.00041000")
    assert details["billable_output_tokens"] == 100


def test_gemini_thinking_and_cache():
    value = call()
    value.provider, value.actual_model = "google", "gemini-3.1-flash-lite"
    value.usage = {"thoughts_token_count": 50, "cached_content_token_count": 500}
    amount, details = estimate(value, snapshot({}))
    assert amount == Decimal("0.00036250")
    assert details["billable_output_tokens"] == 150


@pytest.mark.parametrize(
    "change,status",
    [
        ({"actual_model": "unknown"}, "UNKNOWN_PRICE"),
        ({"status": "FAILED"}, "UNKNOWN_USAGE"),
        ({"input_tokens": None}, "UNKNOWN_USAGE"),
        ({"input_tokens": -1}, "UNKNOWN_USAGE"),
        ({"usage": {"input_tokens_details": {"cached_tokens": 1001}}}, "UNKNOWN_USAGE"),
        ({"usage": {"input_tokens_details": {"cache_write_tokens": 1}}}, "UNSUPPORTED_USAGE"),
        ({"usage": {"service_tier": "priority"}}, "UNSUPPORTED_USAGE"),
    ],
)
def test_unknown_is_not_zero(change, status):
    value = call()
    for key, item in change.items():
        setattr(value, key, item)
    amount, details = estimate(value, snapshot({}))
    assert amount is None and details["status"] == status


def test_skipped_is_zero_and_snapshot_is_independent():
    value = call()
    value.status = "SKIPPED"
    assert estimate(value, {})[0] == 0
    first = snapshot({})
    second = snapshot(
        {"gpt-4.1-mini": {"provider": "openai", "input": "2", "cached": "1", "output": "4"}}
    )
    assert first["rates"]["gpt-4.1-mini"]["input"] == "0.40"
    assert first["fingerprint"] != second["fingerprint"]
