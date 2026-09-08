# Session Code Review Guide

Use this as the directory map for learning the project. Review the implementation after each session before moving to another phase. Session reports list the specific changed files; this guide explains how the existing pieces fit together.

## Current project: Phases 1–3

| Directory/files | Responsibility | Suggested review question |
| --- | --- | --- |
| `forge.md/` | Source-of-truth product, architecture, contracts, phase plan, working rules | What requirement authorizes this change? |
| `src/forge/main.py` | Creates FastAPI, owns resource lifespan, request trace IDs and unexpected-error boundary | When are resources created and closed? |
| `src/forge/core/config.py` | Loads and validates settings | What is required, and how are credentials represented? |
| `src/forge/core/errors.py` | Maps domain/HTTP/validation errors into the API contract | Can errors expose sensitive inputs? |
| `src/forge/db/base.py` | ORM base and naming conventions for future tables | What schema conventions will migrations use? |
| `src/forge/db/session.py` | Async engine, session factory, session dependency | Who commits, rolls back, and closes connections? |
| `src/forge/api/health.py` | Thin liveness/readiness routes | Is database work delegated to a service? |
| `src/forge/health/service.py` | Bounded database connectivity check | What happens on failure or timeout? |
| `src/forge/**/__init__.py` | Python package markers | These currently contain no behavior. |
| `migrations/env.py`, `alembic.ini` | Migration execution and configuration | Why is migration separate from API startup? |
| `migrations/versions/0001_foundation.py` | Empty migration baseline | Why do domain tables wait for Phase 2? |
| `migrations/script.py.mako` | Template for later migration files | What does a new revision need? |
| `tests/test_foundation.py` | Settings, health, timeout, errors, cleanup tests | Which behavior would a regression break? |
| `tests/test_postgres.py` | Real PostgreSQL migration and readiness test | Is the database disposable before downgrade? |
| `pyproject.toml`, `uv.lock`, `.python-version` | Package/dependencies, resolved versions, Python selection | Which dependencies are direct and why? |
| `Dockerfile`, `docker-compose.yml` | Container build and local service startup | Does migration finish before the API starts? |
| `.github/workflows/ci.yml` | Automated checks | Which checks ran locally versus only being configured? |
| `.env.example`, `.gitignore`, `.dockerignore` | Example settings and exclusions | Are local credentials/artifacts excluded? |
| `README.md` | Setup and verification commands | Can someone else run the current phase? |
| `docs/` | Review guides and session implementation records | What changed this session and what remains? |

`.venv/`, `.tools/`, caches, and `dist/` are generated local artifacts, not application source. Review their purpose and dependency lock rather than reading their generated contents line by line.

## First reading order

1. Read `forge.md/00_INDEX.md`, `02_SYSTEM_ARCHITECTURE.md`, and `10_CODEX_WORKING_RULES.md`.
2. Read `README.md`, `pyproject.toml`, and `.env.example`.
3. Follow `src/forge/main.py` into `core/config.py` and `db/session.py`.
4. Follow the health router into `health/service.py`, then read `core/errors.py`.
5. Read `db/base.py` and the migration files.
6. Read both test files and compare assertions with the API contract.
7. Read Docker/Compose/CI, then the session report's results and limitations.
8. Read `forge.md/14_FORGE_RUNTIME_DECISION.md` to understand the planned agent execution before Phase 3.

## Walkthrough: database readiness

```text
Uvicorn calls create_app()
  → Settings loads configuration
  → lifespan creates Database and its async pool
GET /api/v1/health/ready
  → middleware creates trace ID
  → health router calls check_database()
  → bounded SELECT 1 succeeds: 200 {status: ready}
  → database failure: DomainError → structured 503 + matching trace ID
Shutdown → lifespan disposes database engine
```

`main.py` starts the HTTP application and registers registry/run routes. Agent definitions live in `agents/`; Phase 3 execution now lives in `runtime/` and model adapters in `model_router/`.

## Required session handoff

For each session, supply:

1. Scope completed and behavior changed, in plain language.
2. Every added/modified/deleted file, grouped by directory, with purpose and relationships.
3. Dependency/configuration/migration changes and why they are needed.
4. Recommended reading order and a concrete request or failure walkthrough.
5. Commands executed, tests/results, and checks that could not run.
6. Review questions, unresolved issues, and the next phase without beginning it automatically.

Keep historical reports as records of what was true then. New decisions belong in new session notes and current specs, rather than silently rewriting old verification results.


## Phase 2 review path

Read `forge.md/03_AGENT_DEFINITION_AND_REGISTRY.md` and the Phase 2 section of `08_API_CONTRACT.md`, then:

| Order / file | Responsibility and relationship |
| --- | --- |
| 1. `src/forge/agents/schemas.py` | Request/response shapes; validates names, references, limits and editable fields. |
| 2. `src/forge/agents/lifecycle.py` | State names and allowed transitions; used by the service. |
| 3. `src/forge/agents/models.py` | Organization, agent, immutable-version ORM tables. |
| 4. `src/forge/agents/repository.py` | Organization-scoped SQL queries and row locks; called by the service. |
| 5. `src/forge/agents/service.py` | Business validation and commits; calls repository and lifecycle rules. |
| 6. `src/forge/api/registry.py` | Development scope dependency, production block, thin routes calling services. |
| 7. `src/forge/main.py` | Registers the registry router alongside health. |
| 8. `migrations/versions/0002_agent_registry.py` | Tables and PostgreSQL immutability/lifecycle triggers. |
| 9. `migrations/env.py` | Imports registry model metadata for migration comparison. |
| 10. `tests/test_registry_validation.py`, `tests/test_registry_postgres.py` | Invalid input, scope isolation, history, concurrency and database guard checks. |
| 11. `tests/test_postgres.py` | Migration round trip now expects Phase 2 head. |

`src/forge/agents/__init__.py` is a package marker; no hidden behavior. LangChain/LangGraph are not required by the current design.

### Walkthrough: create version v2

```text
POST /api/v1/agents/{agent_id}/versions + X-Organization-ID
  → reject production access until authenticated membership exists
  → VersionCreate validates configuration (client cannot set lifecycle)
  → RegistryService resolves organization-scoped agent with row lock
  → reject inactive agent
  → Repository adds AgentVersion containing the complete configuration snapshot
  → PostgreSQL checks agent/version uniqueness and DRAFT-only insertion
  → Service commits; API returns 201 with exact snapshot and UUID
```

A concurrent duplicate creates no second version and gets 409. Updating the agent's name later does not alter the version. Direct SQL edits of version configuration, DELETE, and TRUNCATE are rejected by database triggers. These guards are not protection from a database administrator deliberately disabling them.

Questions for your review: Which fields can change? Where is organization scoping applied? Why is the organization header not authentication? Why is staging blocked? How do row locks and unique constraints differ? Which rules are enforced by both service and database?


## Phase 3: functions and provider calling side by side

Read the Phase 3 execution contract in `forge.md/04_RUNTIME_AND_STATE_MACHINE.md`, then follow this map:

| File / function | Input → output | Role and caller |
| --- | --- | --- |
| `runtime/schemas.py`: RunCreate/RunRead | JSON version ID/message → validated request; stored run → response | Defines the API boundary |
| `api/runs.py`: create_run | Request, organization and idempotency headers → 201 new run or 200 existing run | Thin route calls RunService.execute |
| `api/runs.py`: get_adapter | Server settings → GeminiAdapter or FakeAdapter | Chooses the explicitly configured backend |
| `runtime/repository.py`: by_key | Organization/key → existing run or none | Prevents duplicate provider execution |
| `runtime/repository.py`: version | Organization/version ID → locked version and parent status | Ensures scoped, exact configuration selection |
| `runtime/service.py`: execute | Validated request + adapter → saved run | Checks configuration, commits intent, calls model, persists outcome |
| `runtime/service.py`: transition | Run/current state + target → incremented version and event | Uses state.py to reject invalid transitions |
| `model_router/base.py` | ModelRequest/ModelResult/ModelFailure | Small provider-neutral interface shared by two adapters |
| `model_router/gemini.py`: generate | ModelRequest → Google SDK request → ModelResult | The external model call; one attempt, no automatic tool execution |
| `model_router/gemini.py`: parse_response | Google response → text, model revision, usage, tool requests, finish reason | Excludes thought text; records usage metadata |
| `model_router/fake.py`: generate | Input message → labelled deterministic echo | Local demo/test provider; no AI/network call |
| `runtime/models.py` | Run/event/model-call records → PostgreSQL tables | Used by service/repository, registered in migrations/env.py |
| `api/runs.py`: get_run/get_events/get_model_calls | Organization/run ID → persisted evidence | Calls scoped read methods; no model call |

### Concrete execution walkthrough

```text
POST /api/v1/runs
  X-Organization-ID: your organization UUID
  Idempotency-Key: first-run
  body: {agent_version_id: your version UUID, input: {message: "Hello"}}

create_run()
  → RunService.execute()
  → by_key(): return old run if key/input already exists
  → version(): verify ownership, active agent, supported exact version
  → commit run RUNNING + CREATED/RUNNING events + model-call intent
  → adapter.generate(ModelRequest)
      fake: return labelled echo
      gemini: client.models.generate_content(model, contents, config)
  → save output/usage or sanitized error
  → commit terminal state + model-call result + terminal event
  → return run resource
```

The first commit releases database locks before waiting on the provider. Repeated requests can read the RUNNING record and never become another executor. The terminal commit keeps result/evidence/event together. Final-write/process failures can leave the first record RUNNING; recovery comes later.

### Ordinary functions versus model tool calling

| What happens now | What is deferred |
| --- | --- |
| Python route calls service, service calls adapter | Model requests a business tool like lookup_customer |
| Gemini adapter asks a model for text | Tool Hub validates and invokes a tool handler (Phase 4) |
| Parser detects unexpected function-call output | Policy and approval authorize high-impact execution (Phase 5) |
| Runtime fails an unexpected tool request without executing it | Looping model → tool → model |

A model-call record means FORGE invoked the model, not that the model invoked a tool. `model_calls_count=1` and `tool_calls_count=0` make that visible. A 201 response means the run was saved; check status to see whether execution succeeded. Fake mode is explicitly labelled and has no provider charges. Real monetary cost is unknown in this phase and dollar budgets are not enforced yet.

Review questions: Where is configuration pinned? What survives before the network call? Why can a duplicate return RUNNING? How are provider errors sanitized? Why does a truncated/blocked answer fail? Where are tools prevented from executing?

Review `tests/test_runtime.py` for adapter/state tests and `tests/test_runtime_postgres.py` for actual persistence, scoping, Unicode, usage, errors and concurrency. New migration: `0003_initial_runtime.py`. Full commands/results and every changed file appear in `PHASE_3_IMPLEMENTATION_REPORT.md`.

## Local frontend session — supported F1–F3 slice

The user requested a frontend early to simplify local testing. Read the scope table at the beginning of `forge.md/FORGE_FRONTEND_SPEC.md` first: the full document is the future blueprint, not a claim that the production control plane exists.

The console runs at **http://127.0.0.1:3000**, with the existing API on **8000**. Its complete inventory, commands, and results are in [FRONTEND_LOCAL_CONSOLE_SESSION.md](FRONTEND_LOCAL_CONSOLE_SESSION.md). Startup and a first test are in [web/README.md](../web/README.md).

### Recommended reading order

1. `web/lib/api/types.ts`: the backend records the UI consumes.
2. `web/lib/schemas.ts`: client-side form validation matching the supported API fields.
3. `web/lib/api/client.ts`: HTTP requests, organization headers, and structured errors.
4. `web/lib/api/forge.ts`: named functions for each supported backend endpoint.
5. `web/app/api/forge/[...path]/route.ts`: restricted same-origin bridge to FastAPI.
6. `web/lib/storage.ts` and `web/components/layout/providers.tsx`: browser workspace context, scoped query cache, and recent run IDs.
7. `web/components/workspace/workspace-screen.tsx`: creating or connecting your organization once.
8. `web/components/agents/agent-screens.tsx`, `version-form.tsx`, and `version-screens.tsx`: identity, immutable configuration, cloning, and confirmed archive.
9. `web/components/runs/playground-screen.tsx`: form submission, one idempotency key per attempt, and uncertain-outcome retry.
10. `web/components/runs/run-detail-screen.tsx`: backend status, output, events, model evidence, and active-run polling.
11. `web/app/` page files, `components/layout/app-shell.tsx`, and `components/ui/`: thin route entry points and shared presentation.
12. `web/tests/`: form/API/proxy unit tests and real-browser integration checks.

### Follow the Run agent button

```text
PlaygroundScreen form
  → React Hook Form validates with runSchema
  → create one UUID Idempotency-Key and retain request in memory
  → TanStack mutation calls api.createRun(org, body, key)
  → request() adds organization header and serializes HTTP request
  → Next.js POST /api/forge/runs validates route/origin and forwards
  → FastAPI POST /api/v1/runs
  → existing RunService.execute() and model adapter
  → persisted RunRead response
  → remember run ID for this browser/workspace
  → navigate to RunDetailScreen
  → GET run, events, and model calls from FastAPI
```

The frontend does not execute agent business logic. Its TypeScript functions call the API; the backend invokes the model adapter. Model-requested business tool execution is still deferred. The inspector explicitly distinguishes **model calls** from **tool calls**, and marks fake execution.

### Questions for your review

- Where is `X-Organization-ID` filled in automatically? Why is it context rather than authentication?
- Why do the query keys include the organization ID?
- Why is saving an agent separate from saving its first version?
- Where does the original run key survive an uncertain network response? What is lost on reload?
- Why can HTTP 201 lead to a FAILED run screen?
- Why is unknown monetary cost displayed differently from fake zero cost?
- Which information is stored in the browser, and which is fetched from the database?
- Why are staging, tool execution, evaluations, and deployment absent from the working navigation?

No backend source, API contract, or database migration was changed in this frontend session. Existing uncommitted runtime/reversal work remains separate. Nothing was pushed to GitHub during this session.

## Phase 4 — Tool Hub and the model/tool loop

The previous sections describe their individual milestones. **Current implementation now includes Phase 4**, with three installed local demo tools and a console extension. Full scope, every changed file, migration, commands, results, and limitations are in [PHASE_4_IMPLEMENTATION_REPORT.md](PHASE_4_IMPLEMENTATION_REPORT.md).

Read in this order:

1. `src/forge/tools/builtins.py`: the three input/output schemas, immutable installed metadata, synthetic customers/transactions, and local ticket handler.
2. `src/forge/tools/models.py` and `migrations/versions/0004_tool_hub.py`: tools, exact agent permissions, recorded calls, local tickets, and database guards.
3. `src/forge/tools/registry.py` and `repository.py`: organization-scoped registration, reads, active status, and exact-revision validation.
4. `src/forge/agents/service.py`: new version creation validates and saves tool bindings; an existing version never changes.
5. `src/forge/tools/policy.py`: the local-demo-only deterministic ALLOW/DENY boundary. This is not yet the Phase 5 business policy engine.
6. `src/forge/tools/hub.py`: argument validation, permissions, stable intent, current status/policy, bounded execution, output validation, and atomic local results.
7. `src/forge/runtime/engine.py` and `events.py`: bounded model turns, serial tool calls, continuation, and monotonic event/state versions.
8. `src/forge/runtime/service.py`: exact-version preflight, idempotent run creation, invoking the engine, and terminal persistence.
9. `src/forge/model_router/base.py`, `fake.py`, and `gemini.py`: neutral tool exchanges, explicit fake commands, and manually controlled Gemini function calling.
10. `src/forge/api/tools.py`: thin development-only HTTP endpoints.
11. `web/components/tools/`, `web/components/agents/version-form.tsx`, and `web/components/runs/playground-screen.tsx`: registration → permission selection → example request. `run-detail-screen.tsx` mounts the tool-call inspector.
12. `tests/test_tools.py`, `tests/test_tools_postgres.py`, and `web/tests/e2e/console.spec.ts`: denied requests, isolation, rollback, timeouts, immutable metadata, tool result reuse, and the full browser journey.

### Function calling, side by side

| Ordinary application function | Model-requested tool call |
| --- | --- |
| A click handler calls `api.createRun(...)`. | The model returns `{name: "lookup_customer", arguments: {customer_id: "cust_001"}}`. |
| `request(...)` sends HTTP to FastAPI. | This is data describing a requested action; it is not executable code or authorization. |
| `RunService.execute(...)` starts the runtime engine. | `ToolHub.execute(...)` validates that data and the version's permission. |
| `RuntimeEngine.model_step(...)` calls the provider adapter. | Only an allowed call reaches `execute_builtin(...)`; output is validated and saved. |
| After a tool result, the engine calls the model again. | The model uses the tool result to produce a final answer or request another permitted tool within limits. |

In fake mode, `/tool` commands simulate the model-request data. They still invoke the real Tool Hub and, for `create_ticket`, the real local database handler. No AI provider is called. Gemini uses schema declarations and manually supplied function responses; the SDK is not permitted to execute Python tools automatically.

### A complete customer lookup

```text
Tools → register lookup_customer 1.0.0
  → POST /tools → ToolRegistry.register → immutable Tool row

Clone agent version → check lookup_customer → save
  → POST /agents/{id}/versions → RegistryService.create_version
  → ToolRegistry.resolve → AgentVersion + AgentTool binding

Test version → /tool lookup_customer {"customer_id":"cust_001"}
  → POST /runs → RunService.execute → RuntimeEngine
  → FakeAdapter returns a function request (real Gemini can request the same schema)
  → WAITING_FOR_TOOL
  → ToolHub: schema → permission → current status/policy → limits
  → execute_builtin → synthetic customer result → output validation → commit
  → RUNNING → model receives tool result → final answer → COMPLETED
  → inspector GETs model-calls and tool-calls
```

Review questions: Why does registering a tool not give every agent permission? Why are tools selected on a new version? What happens if a tool is disabled during the model call? Where is a local ticket rolled back after invalid output? Which transaction closes the local write/result gap? Why does that not prove safety for an external helpdesk? Why must a RUNNING tool call with unknown outcome never be blindly reexecuted? Which event shows the exact tool call and which model turn requested it?

Phase 5 remains the next stage after review: business policies, refunds, approvals, and persistent pause/resume. No Phase 5 approval UI or execution has been implemented in this session.
