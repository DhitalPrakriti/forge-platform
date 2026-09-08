import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from google.genai import errors, types
from pydantic import ValidationError

from forge.core.errors import DomainError
from forge.model_router.base import ModelFailure, ModelRequest
from forge.model_router.gemini import GeminiAdapter, parse_response
from forge.runtime.schemas import RunCreate
from forge.runtime.state import TERMINAL, RunState, validate_transition


@pytest.mark.parametrize("state", list(TERMINAL))
def test_terminal_states_cannot_restart(state):
    with pytest.raises(DomainError):
        validate_transition(state, RunState.RUNNING)


def test_synchronous_transition_and_invalid_path():
    validate_transition(RunState.CREATED, RunState.RUNNING)
    validate_transition(RunState.RUNNING, RunState.COMPLETED)
    validate_transition(RunState.WAITING_FOR_APPROVAL, RunState.TIMED_OUT)
    with pytest.raises(DomainError):
        validate_transition(RunState.CREATED, RunState.COMPLETED)


@pytest.mark.parametrize("message", ["", "   ", "a" * 20001])
def test_run_input_validation(message):
    with pytest.raises(ValidationError):
        RunCreate(agent_version_id=uuid4(), input={"message": message})


def test_gemini_requires_key_and_supported_model():
    with pytest.raises(DomainError) as error:
        GeminiAdapter(None).validate("gemini-example")
    assert error.value.code == "MODEL_NOT_CONFIGURED"
    with pytest.raises(DomainError) as error:
        GeminiAdapter("not-real").validate("unsupported")
    assert error.value.code == "MODEL_UNSUPPORTED"


def test_parse_response_excludes_thoughts_and_preserves_usage():
    result = parse_response(
        types.GenerateContentResponse(
            model_version="gemini-revision-123",
            candidates=[
                types.Candidate(
                    finish_reason="STOP",
                    content=types.Content(
                        parts=[
                            types.Part(text="private reasoning", thought=True),
                            types.Part(text="Answer"),
                            types.Part(
                                function_call=types.FunctionCall(name="unapproved", args={"x": 1})
                            ),
                        ]
                    ),
                )
            ],
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=12,
                candidates_token_count=5,
                thoughts_token_count=7,
                total_token_count=24,
            ),
        )
    )
    assert result.text == "Answer"
    assert result.input_tokens == 12 and result.output_tokens == 5
    assert result.usage["thoughts_token_count"] == 7
    assert result.actual_model == "gemini-revision-123"
    assert result.tool_requests == [{"name": "unapproved", "arguments": {"x": 1}}]
    assert parse_response(types.GenerateContentResponse()).text == ""


@pytest.mark.parametrize(
    "failure, expected",
    [
        (None, None),
        (errors.APIError(403, {"error": {"message": "private credential"}}), "MODEL_AUTH_FAILED"),
        (
            errors.APIError(429, {"error": {"message": "private input"}}),
            "MODEL_PROVIDER_UNAVAILABLE",
        ),
        (
            errors.APIError(503, {"error": {"message": "private input"}}),
            "MODEL_PROVIDER_UNAVAILABLE",
        ),
        (errors.APIError(400, {"error": {"message": "private input"}}), "MODEL_REQUEST_REJECTED"),
        (httpx.ReadTimeout("private input"), "MODEL_TIMEOUT"),
        (httpx.ConnectError("private input"), "MODEL_PROVIDER_UNAVAILABLE"),
    ],
)
def test_gemini_sdk_boundary(monkeypatch, failure, expected):
    generate = AsyncMock(
        return_value=types.GenerateContentResponse(
            model_version="gemini-exact",
            candidates=[
                types.Candidate(
                    finish_reason="STOP", content=types.Content(parts=[types.Part(text="Hello")])
                )
            ],
        ),
        side_effect=failure,
    )
    close = AsyncMock()
    options = {}

    class Client:
        models = SimpleNamespace(generate_content=generate)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            await close()

    def factory(**kwargs):
        options.update(kwargs)
        return SimpleNamespace(aio=Client())

    monkeypatch.setattr("forge.model_router.gemini.genai.Client", factory)
    request = ModelRequest("gemini-example", "Help", "Be concise", "Hi", 2, 100)
    if expected:
        with pytest.raises(ModelFailure) as error:
            asyncio.run(GeminiAdapter("not-real").generate(request))
        assert str(error.value) == expected
        assert "private" not in str(error.value)
    else:
        result = asyncio.run(GeminiAdapter("not-real").generate(request))
        assert result.text == "Hello"
    assert options["http_options"].timeout == 2000
    assert options["http_options"].retry_options.attempts == 1
    config = generate.call_args.kwargs["config"]
    assert config.system_instruction == "Goal: Help\n\nBe concise"
    assert config.automatic_function_calling.disable is True
    assert config.tools is None
    assert generate.call_args.kwargs["contents"] == "Hi"
    close.assert_awaited_once()
