import json

from forge.model_router.base import ModelFailure, ModelRequest, ModelResult


class FakeAdapter:
    """Explicit local demo; never presented as a real model response."""

    provider = "fake"

    def validate(self, model: str) -> None:
        pass

    async def generate(self, request: ModelRequest) -> ModelResult:
        if request.exchanges:
            return ModelResult(
                text="[FAKE MODEL — no provider call] Tool results:\n"
                + json.dumps(
                    request.exchanges[-1].results,
                    indent=2,
                    ensure_ascii=False,
                ),
                actual_model="forge-fake-v1",
                input_tokens=0,
                output_tokens=0,
                usage={"simulated": True},
                finish_reason="STOP",
            )
        if request.message.startswith("/tool "):
            try:
                _, name, raw = request.message.split(" ", 2)
                arguments = json.loads(raw)
            except (ValueError, TypeError):
                raise ModelFailure("FAKE_TOOL_REQUEST_INVALID") from None
            return ModelResult(
                text="",
                actual_model="forge-fake-v1",
                input_tokens=0,
                output_tokens=0,
                usage={"simulated": True},
                tool_requests=[{"name": name, "arguments": arguments}],
                finish_reason="STOP",
            )
        return ModelResult(
            text=f"[FAKE MODEL — no provider call] {request.message}",
            actual_model="forge-fake-v1",
            input_tokens=0,
            output_tokens=0,
            usage={"simulated": True},
            finish_reason="STOP",
        )
