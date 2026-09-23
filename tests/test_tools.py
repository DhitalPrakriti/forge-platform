import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from google.genai import types

from forge.model_router.base import ModelRequest, ToolExchange
from forge.model_router.gemini import GeminiAdapter, parse_response
from forge.runtime.models import Run
from forge.tools.builtins import DEFINITIONS, ToolFailure
from forge.tools.hub import ToolHub
from forge.tools.models import Tool, ToolCall
from forge.tools.policy import decision


def test_policy_does_not_trust_model_authorization_or_modified_metadata():
    definition = DEFINITIONS["create_ticket"]
    tool = Tool(status="ACTIVE", **definition.metadata())
    assert decision(tool, definition) == "ALLOW"
    for field, value in [
        ("status", "INACTIVE"),
        ("risk_level", "HIGH"),
        ("handler_type", "REMOTE"),
        ("idempotency_supported", False),
    ]:
        changed = Tool(status="ACTIVE", **definition.metadata())
        setattr(changed, field, value)
        assert decision(changed, definition) == "DENY"


def test_unknown_tool_outcome_cannot_be_reexecuted():
    call = ToolCall(status="RUNNING", request_hash="same")
    with pytest.raises(ToolFailure, match="TOOL_OUTCOME_UNKNOWN"):
        ToolHub.reuse(call, "same")
    call.status = "COMPLETED"
    with pytest.raises(ToolFailure, match="TOOL_IDEMPOTENCY_CONFLICT"):
        ToolHub.reuse(call, "changed")
    assert ToolHub.reuse(call, "same") is call


def test_terminal_run_cannot_start_a_new_tool_call():
    session = Mock()
    hub = ToolHub(session)
    hub.repository.call = AsyncMock(return_value=None)
    with pytest.raises(ToolFailure, match="INVALID_RUN_STATE"):
        asyncio.run(
            hub.execute(
                Run(status="COMPLETED"), None, 0, {"name": "unknown", "arguments": {}}, [], 5
            )
        )
    session.add.assert_not_called()


def test_gemini_manual_function_exchange_preserves_ids_and_opaque_content(monkeypatch):
    content = types.Content(
        role="model",
        parts=[
            types.Part(text="private thought", thought=True),
            types.Part(
                function_call=types.FunctionCall(
                    id="provider-call-1", name="lookup_customer", args={"customer_id": "cust_001"}
                ),
                thought_signature=b"opaque-signature",
            ),
        ],
    )
    result = parse_response(
        types.GenerateContentResponse(
            candidates=[types.Candidate(content=content, finish_reason="STOP")]
        )
    )
    assert result.text == "" and "private thought" not in repr(result)
    assert result.tool_requests[0]["id"] == "provider-call-1"
    generate = AsyncMock(
        return_value=types.GenerateContentResponse(
            candidates=[
                types.Candidate(
                    content=types.Content(role="model", parts=[types.Part(text="Alex is on Pro.")]),
                    finish_reason="STOP",
                )
            ]
        )
    )

    class Client:
        models = SimpleNamespace(generate_content=generate)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(
        "forge.model_router.gemini.genai.Client", lambda **kwargs: SimpleNamespace(aio=Client())
    )
    request = ModelRequest(
        "gemini-example",
        "Help",
        "Be concise",
        "Who is cust_001?",
        2,
        100,
        tools=[DEFINITIONS["lookup_customer"].metadata()],
        exchanges=[
            ToolExchange(
                response=result,
                results=[
                    {
                        "name": "lookup_customer",
                        "id": "provider-call-1",
                        "result": {"display_name": "Alex Demo"},
                    }
                ],
            )
        ],
    )
    output = asyncio.run(GeminiAdapter("not-real").generate(request))
    assert output.text == "Alex is on Pro."
    sent = generate.call_args.kwargs
    assert sent["config"].automatic_function_calling.disable is True
    declaration = sent["config"].tools[0].function_declarations[0]
    assert declaration.name == "lookup_customer" and declaration.parameters_json_schema
    assert sent["contents"][1] is content
    assert sent["contents"][1].parts[1].thought_signature == b"opaque-signature"
    response = sent["contents"][2].parts[0].function_response
    assert response.id == "provider-call-1" and response.response == {
        "result": {"display_name": "Alex Demo"}
    }
