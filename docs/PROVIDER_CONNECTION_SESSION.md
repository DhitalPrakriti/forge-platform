# Gemini and OpenAI provider connection

This session implements the provider-connection slice of Phase 7: OpenAI Responses API, shared model-based selection, configuration, and durable tool continuation. It does not complete Phase 7: automatic fallback, provider health/circuit breakers, price accounting, and monetary enforcement remain outstanding.

## Behavior

`FORGE_MODEL_BACKEND=routed` selects Gemini for `gemini-` model identifiers and OpenAI for supported OpenAI text-model prefixes (`gpt-`, `o1`, `o3`, `o4`). Prefix validation is not a promise of account access or capability; providers validate exact model availability. Explicit `fake`, `gemini`, and `openai` modes are also supported. Unknown routed identifiers are rejected; no fallback to fake or another paid model happens silently.

API run admission selects and validates a concrete provider, which is pinned in execution configuration. The worker uses the same factory and checks provider compatibility before continuing. Existing fake runs remain fake records; switching the server does not rewrite immutable versions or previous results. Finish pending fake runs before switching backend mode.

OpenAI uses the Responses REST endpoint through existing httpx, with one transport attempt, `store=false`, and encrypted reasoning continuation requested. Only text output, tool requests, and usage are normalized. Private output items remain in protected checkpoints for stateless continuation. Function arguments are decoded and passed through the existing Tool Hub; no provider-side Python tool execution is enabled. Existing Gemini checkpoint decoding remains compatible.

Timeout, authentication, availability, malformed-response, and request errors use controlled codes without exposing provider bodies or keys. The durable runtime continues to own bounded retries. Real costs remain null rather than being fabricated; fake costs remain zero.

## Files changed and reading order

1. `src/forge/model_router/openai.py`: OpenAI HTTP adapter, response parsing, tool continuation, controlled failures.
2. `src/forge/model_router/factory.py`: common API/worker selection and explicit backend modes.
3. `src/forge/core/config.py`: optional secret OpenAI key and routed/openai modes.
4. `src/forge/api/runs.py`: calls shared factory rather than duplicating Gemini construction.
5. `src/forge/runtime/service.py`: resolves concrete provider before run admission and persistence.
6. `src/forge/durability/worker.py`: uses shared factory.
7. `src/forge/durability/engine.py`: resolves per-run adapter and retains provider compatibility checks.
8. `src/forge/approvals/service.py`: resolves the adapter for legacy continuation.
9. `src/forge/runtime/checkpoints.py`: serializes OpenAI JSON continuation while retaining Gemini typed content.
10. `.env.example`: documents OpenAI secret and routed selection.
11. `docker-compose.yml`: forwards OpenAI key to API and worker.
12. `tests/test_openai_adapter.py`: nine credential/selection, checkpoint, request/continuation, error sanitization, and parsing tests using mocked HTTP.
13. `tests/test_durability_postgres.py`: two routed API/worker integration scenarios (Gemini and OpenAI), mocked provider generation with real database/Redis; unknown costs stay null.
14. `README.md`, `docs/CODE_REVIEW_GUIDE.md`, `forge.md/11_PHASED_IMPLEMENTATION_PLAN.md`: connection instructions and scoped progress.
15. `docs/PROVIDER_CONNECTION_SESSION.md`: this report.

No dependencies or database migrations added. Existing user changes to `src/forge/db/session.py` and frontend-generated files were not included. `.tools/model-provider.env` is a private ignored local artifact, not application source.

## Verification

- `uv run ruff check src tests`: passed.
- Existing full suite plus new adapter tests with disposable `forge_test_utf8` and Redis database 1: 128 passed.
- Added routed-provider integration scenarios: 2 passed after the full suite (130 scenarios passed across these runs).
- Existing Starlette test-client deprecation warnings remain; no dependency migration was attempted.
- No live paid API calls were made. Keys/account access and live results still require user configuration.
- No frontend implementation changed, so browser tests/build were not repeated.

## Local connection steps

1. Create provider API keys in Google AI Studio and the OpenAI API platform; configure billing in the provider accounts as needed.
2. Open `.tools/model-provider.env` in the editor and paste keys inside the corresponding single quotes. Do not send keys in chat or record this file.
3. Stop API and worker, then in each backend terminal set the existing local database/Redis/environment settings and `source .tools/model-provider.env`. API also sources `.tools/local-reviewer.env`.
4. Start API with `uv run uvicorn forge.main:create_app --factory --host 127.0.0.1 --port 8000` and worker with `uv run python -m forge.durability.worker`.
5. Clone the fake agent version into a new version using an exact model ID available to your provider account. Save and test a short text prompt. Repeat with a second immutable version for the other provider.
6. Check actual provider/model, response text, usage and outcome in the inspector. A real run should not be marked fake. Costs are not yet calculated or enforced.

The user's $50 total budget is a planning constraint, not an implemented cap. Start with small manual tests and provider-side spending controls while monetary enforcement is pending.

Official API references consulted: https://developers.openai.com/api/docs/guides/function-calling and https://developers.openai.com/api/docs/guides/reasoning . Review question: how does provider-specific continuation survive checkpoints without becoming public model-call evidence?
