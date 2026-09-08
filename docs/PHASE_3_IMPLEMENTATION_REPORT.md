# Phase 3 implementation report

## 1. Implemented functionality

Implemented the FORGE-owned initial in-process runtime. It invokes one model for one exact immutable agent version, stores a run and model-call intent before contacting the provider, and saves the terminal outcome and event together afterward. It supports a real Gemini adapter and an explicitly labelled fake backend for offline local exploration.

New development-only endpoints: POST /api/v1/runs, GET /api/v1/runs/{run_id}, GET /api/v1/runs/{run_id}/events, and GET /api/v1/runs/{run_id}/model-calls. Organization selection remains local/test only; production is blocked by the existing access guard. No deployment alias or full Playground was introduced.

The POST requires Idempotency-Key. Equal organization/key/normalized input returns the existing run, even while RUNNING, without another provider call. Changed payload returns 409. Creation returns 201 regardless of whether the saved model execution succeeded; callers inspect status/output/error_code. Read operations return persisted evidence without contacting a model.

Supports active agents with DRAFT/STAGING standard-agent-v1 versions and no tool/policy/fallback configuration. Rejects unsupported configuration before execution. Runs remain pinned to their selected version even after parent metadata or new versions change. Direct CREATED → RUNNING is documented for this synchronous phase. Terminal states cannot restart; optimistic state_version writes guard against stale updates. Events are ordered and uniquely sequenced.

Gemini uses Google's official async SDK, system instructions from the version's goal/instructions, the persisted input as contents, an explicit output cap, one SDK attempt, and disabled automatic function calling. Requested/actual model, SDK version, available token usage (including additional provider usage metadata), latency, and effective settings are retained. Hidden thought text is not returned as the answer. Empty, blocked, truncated, or tool-request responses fail rather than claim success or execute a tool. Provider exceptions are sanitized to controlled codes.

Dollar cost is not calculated for real calls in Phase 3 and remains null; budget enforcement is explicitly marked NOT_IMPLEMENTED_PHASE_3 in execution_config. Fake external cost is known zero. Monetary estimation/enforcement remains Phase 7. The provider wait timeout is bounded by both server settings and the version's runtime limit. Full runtime deadlines, cancellation, retries/fallback, queue/workers, checkpoint recovery, Tool Hub execution and approvals remain later phases.

## 2. Every file changed in this phase

Earlier uncommitted runtime-reversal edits were preserved. The table below identifies this session's additions/changes rather than attributing every existing dirty file to Phase 3.

| File | Change / purpose |
| --- | --- |
| `src/forge/runtime/__init__.py` (new) | Runtime package marker |
| `src/forge/runtime/state.py` (new) | Run-state enum and valid transition rules |
| `src/forge/runtime/models.py` (new) | Run, RunEvent, ModelCall ORM models and indexes |
| `src/forge/runtime/schemas.py` (new) | Validated input and response shapes; consistent money serialization |
| `src/forge/runtime/repository.py` (new) | Scoped run/version/idempotency/evidence queries |
| `src/forge/runtime/service.py` (new) | Execution orchestration, commits, idempotency, limits, outcome mapping |
| `src/forge/model_router/__init__.py` (new) | Model integration package marker |
| `src/forge/model_router/base.py` (new) | Small provider-neutral request/result/protocol/error interface |
| `src/forge/model_router/gemini.py` (new) | Official SDK adapter and response parsing |
| `src/forge/model_router/fake.py` (new) | Explicit deterministic local demo backend |
| `src/forge/api/runs.py` (new) | Thin run/evidence routes and server-configured adapter selection |
| `src/forge/main.py` | Register run routes |
| `src/forge/core/config.py` | Backend selection, secret Gemini key, model timeout/output cap |
| `.env.example` | Document new settings without credentials |
| `pyproject.toml` | Add google-genai; promote HTTPX from development to runtime use |
| `uv.lock` | Pin resolved SDK and transitive dependencies |
| `migrations/env.py` | Register runtime ORM metadata |
| `migrations/versions/0003_initial_runtime.py` (new) | Runtime tables and constraints; reviewed generated migration |
| `tests/test_runtime.py` (new) | State/input/SDK parsing and error-boundary tests |
| `tests/test_runtime_postgres.py` (new) | Execution, persistence, scoping, idempotency, usage, Unicode and failure tests |
| `tests/test_postgres.py` | Expected migration head updated to 0003_initial_runtime |
| `tests/test_registry_postgres.py` | Truncation-guard test accounts for new foreign keys using CASCADE, still asserting rejection |
| `forge.md/04_RUNTIME_AND_STATE_MACHINE.md` | Concrete Phase 3 execution and phase boundaries |
| `forge.md/07_DATABASE_SCHEMA.md` | Implemented runtime fields and UTF-8 requirement |
| `forge.md/08_API_CONTRACT.md` | New development run endpoint, headers, outcomes and errors |
| `README.md` | Current status, setup, fake/Gemini usage and limitations |
| `docs/CODE_REVIEW_GUIDE.md` | Function-by-function map, call flow and side-by-side tool distinction |
| `docs/PHASE_3_IMPLEMENTATION_REPORT.md` (new) | This report |

New source directories are runtime/ and model_router/. No agent registry business behavior was changed. Existing immutable version rows and prior migration files were preserved. LangChain/LangGraph, Redis and queue packages were not added.

## 3. Migration and dependency details

Migration 0003_initial_runtime follows 0002_agent_registry. Creates runs, model_calls and run_events with UUID/FK relationships, state constraint, unique organization/idempotency key, unique run/event sequence and lookup indexes. Unknown costs/usage are nullable. Run configuration stores provider identity and effective settings; exact prompt/goal/model intent remains recoverable through the immutable version and persisted input. No future deployment/checkpoint/outbox table is introduced. Downgrade removes only the new tables/indexes.

Added google-genai 1.75.0, behind the adapter. HTTPX 0.28.1 was already used for testing and is now an explicit runtime dependency because the Gemini adapter classifies transport exceptions. uv.lock records transitive packages including Google authentication, cryptography, HTTP transport, retry support and websockets; presence of SDK retry support does not enable retries (attempts is explicitly 1). No API key was written to tracked files.

## 4. Tests added and updated

30 new cases bring the suite from 38 to 68. Coverage includes:

- Terminal run states cannot restart; synchronous path works; illegal transitions fail.
- Empty/oversized input validation.
- Missing key and unsupported Gemini model validation.
- Provider response parsing, thought-text exclusion, actual model and token metadata.
- Mocked official SDK request configuration, async cleanup, one attempt, disabled function execution, and sanitized 400/403/429/503/transport/timeout errors.
- Real PostgreSQL successful fake execution, version pinning, state/event sequencing, call evidence, consistent response serialization and idempotency replay/conflict.
- Timeout, provider failure, unexpected exception, unimplemented tool request, and blocked-response persistence.
- Organization scoping, missing idempotency header, archived version and production access rejection.
- Unsupported tools/policies/fallback/template rejection.
- Concurrent duplicate requests return the same RUNNING run and invoke the adapter once.
- Effective timeout selection, exact instruction/message transfer, Unicode text, actual-model/usage persistence and unknown real cost.

Existing migration tests exercise upgrade → downgrade to base → upgrade and Alembic metadata drift. All database tests use a disposable database, not the user's local review database.

## 5. Commands and environment actions

Read specs/runtime/registry/configuration/test code with cat and searched status with git status/diff. Consulted official Google SDK documentation and inspected installed SDK option fields. Wrote files via temporary Python scaffold scripts and heredocs. Main verification commands (repeated invocations consolidated):

```sh
.tools/bin/uv add 'google-genai>=1.0,<2'
.tools/bin/uv add 'httpx>=0.28,<1'
.tools/bin/uv remove --dev httpx
FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_test .tools/bin/uv run alembic revision --autogenerate -m initial_runtime --rev-id 0003_initial_runtime
mv migrations/versions/0003_initial_runtime_initial_runtime.py migrations/versions/0003_initial_runtime.py
.tools/bin/uv run ruff format .
.tools/bin/uv run ruff check . --fix
.tools/bin/uv run ruff check .
.tools/bin/uv run ruff format --check .
FORGE_TEST_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_test .tools/bin/uv run pytest -q
/opt/homebrew/opt/postgresql@16/bin/createdb -h 127.0.0.1 -p 55432 -U forge -E UTF8 -T template0 forge_test_utf8
FORGE_TEST_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_test_utf8 .tools/bin/uv run pytest -q
FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_test_utf8 .tools/bin/uv run alembic check
.tools/bin/uv build
```

SDK/mock tests make no external model calls. Checked only whether Gemini configuration was present, without printing a credential: no key was configured.

Initial tests identified SQL_ASCII encoding in the old disposable test database. Diagnosed using a direct service call against synthetic test data, then created a separate UTF-8 test database. The user's forge_local database was already UTF-8 and was not reset. Updated the truncation test so the new FK no longer masks the intended history-trigger assertion. Fixed zero-cost serialization differing between an immediate response and a later database read. Replaced polling in the concurrency test with a bounded thread event wait. Re-ran the full suite after fixes and the additional usage/Unicode case.

For local exploration, applied forward migration to forge_local and verified metadata:

```sh
FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_local .tools/bin/uv run alembic upgrade head
FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_local .tools/bin/uv run alembic check
UV_PROJECT_ENVIRONMENT=.tools/production-venv .tools/bin/uv sync --frozen --no-dev --no-editable --reinstall-package forge-platform
```

Stopped the previous managed API process with Ctrl-C, then launched the noneditable production-dependency installation in explicitly local/fake mode:

```sh
FORGE_ENVIRONMENT=local FORGE_MODEL_BACKEND=fake FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_local .tools/production-venv/bin/uvicorn forge.main:create_app --factory --host 127.0.0.1 --port 8000
```

A real HTTPX smoke script checked health/docs/OpenAPI, created an isolated demo organization/agent/version, executed a fake run (201), repeated it (200), and read persisted run/events/model-call evidence. Saved ready-to-use local demo headers/body/run ID in ignored `.tools/phase3-demo.json`. Existing user-created organizations were not altered. PostgreSQL and the local fake API remain running for review. Development/build caches and dist artifacts were updated; no global packages were installed this session.

Final documentation validation checked relative links and fenced blocks. No commit, push, PR, hosted CI or Docker execution was performed; earlier local architecture-reversal edits remain alongside this phase's changes.

## 6. Final results

| Check | Result |
| --- | --- |
| Complete suite with PostgreSQL | **68 passed**, 2 existing upstream deprecation warnings |
| Lint and formatting | Passed |
| Migration round trip | Passed |
| Schema drift | No new upgrade operations detected |
| Package source/wheel build | Passed |
| Frozen noneditable production-dependency installation | Passed |
| Live localhost health/docs/OpenAPI | Passed |
| Live fake run creation/replay/read/events/model calls | Passed |
| Mocked Gemini SDK boundary | Passed |
| Real Gemini network invocation | Not run: key not configured |
| Docker/hosted CI | Not run this session |

## 7. Remaining limitations

Gemini integration is implemented and tested with SDK-shaped mocks; a live provider smoke check is still needed once a key is configured privately. Fake output is an echo, not an AI answer. Real calls may cost money; dollar-budget enforcement and estimated pricing remain Phase 7. No tool can execute yet. A process crash or final persistence failure can leave RUNNING records; idempotency prevents automatic duplicate calls but does not provide recovery. Production access remains blocked pending authentication and release/deployment services.

The two warnings are existing Starlette HTTPX/AnyIO deprecations, not suppressed. No claim of Docker/hosted CI success is made.

## 8. Review and next step

Read schemas → state → models → repository → service → provider interface/adapters → routes → migration → tests. The side-by-side function map in CODE_REVIEW_GUIDE.md explains arguments, results, and callers.

At http://127.0.0.1:8000/docs, open runs → POST /api/v1/runs. Use the organization UUID, exact version UUID and a fresh Idempotency-Key. For a pre-created demo, inspect `.tools/phase3-demo.json`; use a new key if you want a new run rather than the smoke-test result. A 201 confirms resource creation; inspect status for execution success.

Phase 4 (Tool Hub and tool calling) is next after review and instruction. No Phase 4 execution was implemented.

## Primary references

The async client, generation configuration and lifecycle were checked against the [official Google Gen AI SDK](https://github.com/googleapis/python-genai) and [SDK documentation](https://googleapis.github.io/python-genai/). HTTP retry/timeout semantics were checked in the [official client implementation](https://github.com/googleapis/python-genai/blob/main/google/genai/_api_client.py). Runtime lifecycle and phase choices are FORGE decisions documented in the specs.
