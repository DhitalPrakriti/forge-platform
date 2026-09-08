from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ModelRequest:
    model: str
    goal: str
    instructions: str
    message: str
    timeout_seconds: float
    max_output_tokens: int
    tools: list[dict] = field(default_factory=list)
    exchanges: list[ToolExchange] = field(default_factory=list, repr=False)


@dataclass(frozen=True)
class ModelResult:
    text: str
    actual_model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    usage: dict = field(default_factory=dict)
    tool_requests: list[dict] = field(default_factory=list)
    finish_reason: str | None = None
    # Ephemeral provider continuation (including opaque signatures); never API/DB evidence.
    provider_content: object | None = field(default=None, repr=False)


@dataclass(frozen=True)
class ToolExchange:
    response: ModelResult
    results: list[dict]


class ModelFailure(Exception):
    # Codes are controlled by adapters, never copied from raw provider exception text.
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ModelAdapter(Protocol):
    provider: str

    def validate(self, model: str) -> None: ...

    async def generate(self, request: ModelRequest) -> ModelResult: ...
