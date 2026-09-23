import asyncio
import json

import httpx
import pytest

from forge.core.config import Settings
from forge.core.errors import DomainError
from forge.model_router.base import ModelFailure, ModelRequest, ToolExchange
from forge.model_router.factory import adapter_for, select_adapter
from forge.model_router.openai import OpenAIAdapter, parse_response
from forge.runtime.checkpoints import load_result, save_result


def request(**kwargs):
    return ModelRequest(
        model="gpt-test",
        goal="review",
        instructions="Explain",
        message="hello",
        timeout_seconds=5,
        max_output_tokens=128,
        **kwargs,
    )


def response():
    return {
        "model": "gpt-test-snapshot",
        "status": "completed",
        "usage": {"input_tokens": 12, "output_tokens": 8},
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Hello"}],
            }
        ],
    }


def test_router_and_credentials():
    settings = Settings(
        database_url="postgresql+asyncpg://localhost/test",
        model_backend="routed",
        openai_api_key="test-key",
        gemini_api_key="test-key",
    )
    router = adapter_for(settings)
    assert select_adapter(router, "gpt-test").provider == "openai"
    assert select_adapter(router, "gemini-test").provider == "google"
    with pytest.raises(DomainError):
        select_adapter(router, "forge-fake-v1")
    with pytest.raises(DomainError):
        OpenAIAdapter(None).validate("gpt-test")
    settings.model_backend = "fake"
    assert select_adapter(adapter_for(settings), "gpt-test").provider == "fake"


def test_tool_checkpoint_roundtrip():
    data = response()
    data["output"] = [
        {"type": "reasoning", "encrypted_content": "opaque", "summary": []},
        {
            "type": "function_call",
            "call_id": "call_1",
            "name": "lookup_customer",
            "arguments": '{"customer_id":"123"}',
        },
    ]
    result = load_result(json.loads(json.dumps(save_result(parse_response(data)))))
    assert result.tool_requests == [
        {"id": "call_1", "name": "lookup_customer", "arguments": {"customer_id": "123"}}
    ]
    assert result.provider_content == {"openai_output": data["output"]}
    assert "opaque" not in repr(result)


def test_http_request_and_continuation(monkeypatch):
    original = httpx.AsyncClient
    prior = response()
    prior["output"] = [
        {"type": "function_call", "call_id": "call_1", "name": "lookup_customer", "arguments": "{}"}
    ]
    exchange = ToolExchange(
        load_result(save_result(parse_response(prior))),
        [{"id": "call_1", "name": "lookup_customer", "result": {"ok": True}}],
    )

    def handler(req):
        body = json.loads(req.content)
        assert req.url == "https://api.openai.com/v1/responses"
        assert req.headers["authorization"] == "Bearer test-key"
        assert body["store"] is False
        assert body["input"][-1]["call_id"] == "call_1"
        assert body["input"][-1]["type"] == "function_call_output"
        assert body["tools"][0]["strict"] is False
        return httpx.Response(200, json=response())

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: original(**kw, transport=httpx.MockTransport(handler))
    )
    result = asyncio.run(
        OpenAIAdapter("test-key").generate(
            request(
                exchanges=[exchange],
                tools=[
                    {
                        "name": "lookup_customer",
                        "description": "Lookup",
                        "input_schema": {"type": "object"},
                    }
                ],
            )
        )
    )
    assert result.text == "Hello"
    assert result.input_tokens == 12
    assert result.output_tokens == 8
    assert result.actual_model == "gpt-test-snapshot"


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "MODEL_AUTH_FAILED"),
        (403, "MODEL_AUTH_FAILED"),
        (429, "MODEL_PROVIDER_UNAVAILABLE"),
        (503, "MODEL_PROVIDER_UNAVAILABLE"),
        (400, "MODEL_REQUEST_REJECTED"),
    ],
)
def test_errors_are_sanitized(monkeypatch, status, code):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original(
            **kw,
            transport=httpx.MockTransport(
                lambda req: httpx.Response(status, text="sensitive-provider-payload")
            ),
        ),
    )
    with pytest.raises(ModelFailure) as failure:
        asyncio.run(OpenAIAdapter("test-key").generate(request()))
    assert str(failure.value) == code


def test_invalid_arguments_and_incomplete():
    data = response()
    data["status"] = "incomplete"
    assert parse_response(data).finish_reason == "INCOMPLETE"
    data["output"] = [{"type": "function_call", "arguments": "[]"}]
    with pytest.raises(ValueError):
        parse_response(data)
