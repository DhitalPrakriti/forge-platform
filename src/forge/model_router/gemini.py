import httpx
from google import genai
from google.genai import errors, types

from forge.core.errors import DomainError
from forge.model_router.base import ModelFailure, ModelRequest, ModelResult


def parse_response(response: types.GenerateContentResponse) -> ModelResult:
    candidate = response.candidates[0] if response.candidates else None
    parts = candidate.content.parts if candidate and candidate.content else []
    text_parts, tool_requests = [], []
    for part in parts or []:
        if part.function_call:
            tool_requests.append(
                {"name": part.function_call.name, "arguments": part.function_call.args or {}}
            )
            if part.function_call.id:
                tool_requests[-1]["id"] = part.function_call.id
        if part.text and not part.thought:
            text_parts.append(part.text)
    usage = response.usage_metadata
    return ModelResult(
        text="".join(text_parts),
        actual_model=response.model_version or "unknown",
        input_tokens=usage.prompt_token_count if usage else None,
        output_tokens=usage.candidates_token_count if usage else None,
        usage=usage.model_dump(mode="json", exclude_none=True) if usage else {},
        tool_requests=tool_requests,
        finish_reason=str(candidate.finish_reason.value)
        if candidate and candidate.finish_reason
        else None,
        provider_content=candidate.content if candidate else None,
    )


class GeminiAdapter:
    provider = "google"

    def __init__(self, api_key: str | None):
        self._api_key = api_key

    def validate(self, model: str) -> None:
        if not self._api_key:
            raise DomainError(
                "MODEL_NOT_CONFIGURED", "Configure FORGE_GEMINI_API_KEY server-side.", 503
            )
        if not model.startswith("gemini-"):
            raise DomainError(
                "MODEL_UNSUPPORTED", "The Gemini adapter requires a Gemini model.", 422
            )

    async def generate(self, request: ModelRequest) -> ModelResult:
        contents = request.message
        if request.exchanges:
            contents = [types.Content(role="user", parts=[types.Part(text=request.message)])]
            for exchange in request.exchanges:
                # Preserve the original content/signatures, including after checkpoint restore.
                contents.append(exchange.response.provider_content)
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name=result["name"],
                                    id=result.get("id"),
                                    response={"result": result["result"]},
                                )
                            )
                            for result in exchange.results
                        ],
                    )
                )
        try:
            # One attempt: retries/fallback are later phases. SDK never executes Python tools.
            async with genai.Client(
                api_key=self._api_key,
                vertexai=False,
                http_options=types.HttpOptions(
                    timeout=max(1, int(request.timeout_seconds * 1000)),
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            ).aio as client:
                response = await client.models.generate_content(
                    model=request.model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=f"Goal: {request.goal}\n\n{request.instructions}",
                        max_output_tokens=request.max_output_tokens,
                        tools=[
                            types.Tool(
                                function_declarations=[
                                    types.FunctionDeclaration(
                                        name=tool["name"],
                                        description=tool["description"],
                                        parameters_json_schema=tool["input_schema"],
                                    )
                                    for tool in request.tools
                                ]
                            )
                        ]
                        if request.tools
                        else None,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(
                            disable=True
                        ),
                    ),
                )
            return parse_response(response)
        except errors.APIError as exc:
            if exc.code in (401, 403):
                code = "MODEL_AUTH_FAILED"
            elif exc.code == 429 or (exc.code is not None and exc.code >= 500):
                code = "MODEL_PROVIDER_UNAVAILABLE"
            else:
                code = "MODEL_REQUEST_REJECTED"
            raise ModelFailure(code) from None
        except (httpx.TimeoutException, TimeoutError):
            raise ModelFailure("MODEL_TIMEOUT") from None
        except httpx.TransportError:
            raise ModelFailure("MODEL_PROVIDER_UNAVAILABLE") from None
