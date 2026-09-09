import json

from google.genai import types

from forge.model_router.base import ModelResult, ToolExchange
from forge.runtime.checkpoints import load_exchanges, save_exchanges


def test_signed_provider_continuation_survives_json_roundtrip():
    content = types.Content(
        role="model",
        parts=[
            types.Part(
                function_call=types.FunctionCall(
                    name="issue_refund",
                    id="call-1",
                    args={"customer_id": "cust_001", "amount_usd": "425.00"},
                ),
                thought_signature=b"\xff\x00signature",
            )
        ],
    )
    original = ToolExchange(
        response=ModelResult(
            text="",
            actual_model="gemini-test",
            provider_content=content,
            tool_requests=[
                {
                    "name": "issue_refund",
                    "arguments": {"customer_id": "cust_001", "amount_usd": "425.00"},
                    "id": "call-1",
                }
            ],
            finish_reason="STOP",
        ),
        results=[{"name": "issue_refund", "id": "call-1", "result": {"demo": True}}],
    )
    restored = load_exchanges(json.loads(json.dumps(save_exchanges([original]))))[0]
    assert restored.response.provider_content == content
    assert restored.results == original.results
    assert "signature" not in repr(restored.response)
