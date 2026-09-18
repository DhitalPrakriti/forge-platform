"""One Responses API attempt; FORGE owns tool execution and retries."""

import json

import httpx

from forge.core.errors import DomainError
from forge.model_router.base import ModelFailure, ModelRequest, ModelResult


def parse_response(data: dict) -> ModelResult:
    output = data.get("output", [])
    texts, calls = [], []
    for item in output:
        if item.get("type") == "message":
            texts.extend(p["text"] for p in item.get("content", []) if p["type"] == "output_text")
        elif item.get("type") == "function_call":
            arguments = json.loads(item["arguments"])
            if not isinstance(arguments, dict):
                raise ValueError("Invalid tool arguments")
            calls.append({"id": item["call_id"], "name": item["name"], "arguments": arguments})
    usage = data.get("usage") or {}
    return ModelResult(
        text="".join(texts),
        actual_model=data.get("model", "unknown"),
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        usage={**usage, "service_tier": data.get("service_tier")},
        tool_requests=calls,
        finish_reason="STOP" if data.get("status") == "completed" else "INCOMPLETE",
        provider_content={"openai_output": output},
    )


class OpenAIAdapter:
    provider = "openai"

    def __init__(self, api_key: str | None):
        self._api_key = api_key

    def validate(self, model: str) -> None:
        if not self._api_key:
            raise DomainError(
                "MODEL_NOT_CONFIGURED", "Configure FORGE_OPENAI_API_KEY server-side.", 503
            )
        if not model.startswith(("gpt-", "o1", "o3", "o4")):
            raise DomainError("MODEL_UNSUPPORTED", "Use an OpenAI text model identifier.", 422)

    async def generate(self, request: ModelRequest) -> ModelResult:
        inputs = [*request.history, {"role": "user", "content": request.message}]
        for exchange in request.exchanges:
            content = exchange.response.provider_content
            if not isinstance(content, dict) or "openai_output" not in content:
                raise ModelFailure("CHECKPOINT_INCOMPATIBLE")
            inputs.extend(content["openai_output"])
            inputs.extend(
                {
                    "type": "function_call_output",
                    "call_id": result["id"],
                    "output": json.dumps(result["result"]),
                }
                for result in exchange.results
            )
        payload = {
            "model": request.model,
            "instructions": f"Goal: {request.goal}\n\n{request.instructions}",
            "input": inputs,
            "max_output_tokens": request.max_output_tokens,
            "store": False,
            "service_tier": "default",
            "include": ["reasoning.encrypted_content"],
            "tools": [
                {
                    "type": "function",
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                    "strict": False,
                }
                for tool in request.tools
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                response = await client.post(
                    "https://api.openai.com/v1/responses",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
            if response.status_code in (401, 403):
                raise ModelFailure("MODEL_AUTH_FAILED")
            if response.status_code == 429 or response.status_code >= 500:
                raise ModelFailure("MODEL_PROVIDER_UNAVAILABLE")
            if not response.is_success:
                raise ModelFailure("MODEL_REQUEST_REJECTED")
            return parse_response(response.json())
        except (httpx.TimeoutException, TimeoutError):
            raise ModelFailure("MODEL_TIMEOUT") from None
        except httpx.TransportError:
            raise ModelFailure("MODEL_PROVIDER_UNAVAILABLE") from None
        except (ValueError, KeyError, TypeError, AttributeError):
            raise ModelFailure("MODEL_RESPONSE_INVALID") from None
