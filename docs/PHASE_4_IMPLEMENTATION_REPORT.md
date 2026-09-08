# Phase 4 — Tool Hub implementation report

## 1. Implemented functionality

Implemented the next stage in `11_PHASED_IMPLEMENTATION_PLAN.md`: **Phase 4, Tool Hub**. Read the phase plan, working rules, tool/policy specification, schema/API/security/runtime documents, current runtime decision, and the existing backend/frontend code before editing. The earlier uncommitted work was preserved.

The console and backend now support a complete local **model → tool → model** flow:

- Register organization-owned immutable `1.0.0` revisions of `lookup_customer`, `lookup_transactions`, and `create_ticket`.
- Serve their authoritative descriptions, input/output schemas, risk, timeout, retry/idempotency metadata, and ACTIVE/INACTIVE status.
- Validate exact tool IDs when creating a new immutable agent version, and save normalized permissions matching its JSON configuration.
- Offer only pinned tool descriptions/input schemas to the model; no Python functions, database connection strings, or provider keys enter the model tool catalog.
- Route every requested function through strict input validation, exact-name permission, current administrative status, installed-metadata/local-policy checks, and bounded execution.
- Persist stable tool-call identity before execution; save normalized arguments, result/error, ALLOW/DENY, latency, hashes/keys, exact tool revision, and requesting model-call ID.
- Validate outputs before committing local effects. An invalid output, handler error, or timeout rolls back a local demo-ticket write through a savepoint.
- Return successful tool results to the model for a final answer, while preserving individual model-call usage and event history.
- Bound model turns by max_steps, requests by eight per model turn and 32 per run, and model/tool work by configured time limits. Tool-lock waiting also consumes its timeout.
- Keep plain text-only fake runs compatible with the original three-event, one-model-call path.
- Provide a Tools console page, version permission checkboxes, explicit fake-tool examples, and a tool-call inspector.

The new runtime identity is `forge-runtime-phase4-v1`. Existing runs keep their original identity and evidence. New execution records identify pinned tool IDs, call caps, `LOCAL_DEMO_ONLY_PHASE_4`, and monetary enforcement `DEFERRED_TO_PHASE_7`.

### What the three tools actually do

| Tool | Arguments | Result / effect |
| --- | --- | --- |
| `lookup_customer` | `customer_id`, e.g. `cust_001` | Synthetic profile: Alex Demo, Pro plan; labelled demo. |
| `lookup_transactions` | `customer_id` | Synthetic transaction list with string USD amount; labelled demo. |
| `create_ticket` | `customer_id`, nonempty `title`, nonempty `details` | Saves an organization-scoped local `demo_tickets` row; returns ticket UUID and OPEN status. No external helpdesk or message is contacted. |

Only sample customers `cust_001` and `cust_002` exist. Other validly formatted IDs return a recorded DEMO_CUSTOMER_NOT_FOUND failure.

### Policy and safety boundary in this phase

The model cannot grant itself permission. Registration alone does not bind a tool to an agent. New versions must explicitly select exact tool revisions. Unknown, unbound, inactive, changed, high-risk, or invalid requests fail closed.

This is a deterministic **local-demo allowlist**, not the Phase 5 policy engine. No `issue_refund`, monetary approval threshold, REQUIRE_APPROVAL execution, reviewer authentication, or persistent approval continuation was added.

## 2. Every file changed or added

Paths are relative to the repository root. This inventory describes **this Phase 4 session**, not all earlier dirty files shown by Git.

### Backend: new tool domain and routes

| File | Purpose and caller relationship |
| --- | --- |
| `src/forge/tools/__init__.py` | Tool domain package. |
| `src/forge/tools/models.py` | SQLAlchemy Tool, AgentTool, ToolCall, and DemoTicket records; used by registry, hub, handlers, and migration metadata. |
| `src/forge/tools/schemas.py` | HTTP registration/status/read/call schemas; rejects arbitrary registration metadata or executable code. |
| `src/forge/tools/builtins.py` | Strict input/output Pydantic models, installed definitions, synthetic fixtures, and `execute_builtin`; called only after Hub validation/authorization. |
| `src/forge/tools/repository.py` | Scoped tool queries, immutable permission IDs, and ordered call reads/reuse lookup. |
| `src/forge/tools/registry.py` | Idempotent installed-tool registration, ownership/status reads, administrative patch, and exact-revision resolution; used by API and agent/runtime preflight. |
| `src/forge/tools/policy.py` | Explicit local-demo-only ALLOW/DENY decision; called immediately before execution. |
| `src/forge/tools/hub.py` | Complete tool boundary: JSON/input validation, permission, stable identity/hash, reuse checks, fresh locked status/policy, timeout, handler/output validation, savepoint rollback, result/events. |
| `src/forge/api/tools.py` | Thin registry GET/POST/PATCH and run tool-call read routes; all use existing development scope/production guard. |

### Backend: runtime/provider integration

| File | Change |
| --- | --- |
| `src/forge/runtime/engine.py` | New bounded execution loop; one recorded model call per turn, serial Tool Hub calls, continuation, limits, and controlled failures. |
| `src/forge/runtime/events.py` | New shared event/transition helpers so tool evidence and run transitions share a monotonic sequence and optimistic version. |
| `src/forge/runtime/service.py` | Resolves pinned tools and normalized permissions; retains run idempotency; delegates execution to the engine and commits terminal state. |
| `src/forge/model_router/base.py` | Adds provider-neutral ToolExchange, schema declarations, and non-repr transient provider continuation to model requests/results. |
| `src/forge/model_router/fake.py` | Explicit `/tool name JSON` test requests and labelled tool-result reply; normal text echo remains available. |
| `src/forge/model_router/gemini.py` | Sends declarations and manual function responses, preserves provider function IDs and signed model content in memory, and keeps SDK automatic execution disabled. |
| `src/forge/agents/service.py` | Validates tool ownership/status/installed metadata, then saves version and immutable normalized bindings; preserves duplicate-version handling. |
| `src/forge/main.py` | Includes the Tool Hub router. |

### Migration and tests

| File | Change |
| --- | --- |
| `migrations/versions/0004_tool_hub.py` | Adds four tables, indexes/uniqueness/FKs, immutable tool metadata guards, and immutable same-org/pinned-ID binding guards. |
| `migrations/env.py` | Registers tool ORM metadata for Alembic. |
| `tests/test_tools.py` | New local policy, unknown-outcome/idempotency conflict, terminal-run protection, and Gemini manual function/signature tests. |
| `tests/test_tools_postgres.py` | New real-database registration/scoping/immutability, all three tool flows, input/permission failures, disable race, local effect rollback, timeout/limits, and result reuse tests. |
| `tests/test_runtime_postgres.py` | Replaces obsolete “tools never implemented” assertions with current denial behavior; permits slightly reduced model timeout because the run deadline now counts elapsed time; removes the superseded blanket tools-unsupported case. |
| `tests/test_registry_postgres.py` | Keeps unresolved policy/evaluation staging coverage without an arbitrary tool ID now that the tool registry validates IDs. |
| `tests/test_postgres.py` | Updates expected migration head to 0004; still tests disposable upgrade → downgrade → upgrade and schema agreement. |

### Frontend: new source

| File | Purpose |
| --- | --- |
| `web/app/tools/page.tsx` | Thin route entry point for ToolsScreen. |
| `web/components/tools/tools-screen.tsx` | Register installed tools, read schemas/metadata, confirm disabling, and re-enable. Calls the actual backend. |
| `web/components/tools/tool-call-inspector.tsx` | Scoped call query and clear arguments/result/decision/error/latency/identity display. |
| `web/lib/tool-demo.ts` | Explicit, documented fake-backend input examples; buttons fill the message box, not synthetic results. |

### Frontend: updated source

| File | Change |
| --- | --- |
| `web/lib/api/types.ts` | Adds typed tool metadata, installed names, and recorded tool-call shapes. |
| `web/lib/api/forge.ts` | Centralized register/list/status/tool-call endpoint functions. |
| `web/lib/schemas.ts` | Validates exact UUID tool selections on new versions. |
| `web/app/api/forge/[...path]/route.ts` | Adds only the supported tool paths and restricted tool-status PATCH to the existing proxy. |
| `web/components/agents/version-form.tsx` | Reads registered tools; supports exact-revision checkboxes, cloning with retained selections, removing unavailable dependencies, and updated model-step guidance. |
| `web/components/agents/version-screens.tsx` | Updates feature availability copy for Phase 4. |
| `web/components/layout/app-shell.tsx` | Adds Tools navigation and Phase 4 footer. |
| `web/components/overview/overview-screen.tsx` | Reflects the model/tool runtime instead of the former single-call-only capability. |
| `web/components/runs/playground-screen.tsx` | Fake-tool example controls and the model/tool explanation; retains run retry-key behavior. |
| `web/components/runs/run-detail-screen.tsx` | Polls WAITING_FOR_TOOL, refreshes tool evidence on transitions, and mounts ToolCallInspector. |
| `web/components/ui/confirm-dialog.tsx` | Reuses the existing accessible confirmation primitive with configurable labels for tool disabling; archive behavior retained. |
| `web/app/globals.css` | Tool cards, permission rows, readable JSON, decision colors, and five-item mobile navigation without horizontal overflow. |
| `web/tests/forms-and-storage.test.tsx` | Extends valid version-form fixture for tool selections. |
| `web/tests/e2e/console.spec.ts` | New register → clone/bind → ticket → inspector → unbound denial → disable/re-enable browser test; existing polling fixture includes tool reads. |

### Documentation

| File | Change |
| --- | --- |
| `README.md` | Current Phase 4 status and tool-testing instructions. |
| `web/README.md` | Step-by-step browser workflow and distinction between fake model and real local tool execution. |
| `forge.md/00_INDEX.md` | Links this report. |
| `forge.md/04_RUNTIME_AND_STATE_MACHINE.md` | Adds current loop/event/limit/continuation contract while retaining the Phase 3 milestone. |
| `forge.md/05_TOOLS_POLICIES_APPROVALS.md` | Defines installed demo scope, boundary, atomic local effects, and deferred approvals. |
| `forge.md/07_DATABASE_SCHEMA.md` | Documents actual four-table migration and nullable ID rationale for rejected requests. |
| `forge.md/08_API_CONTRACT.md` | Documents registration, read/status/call routes and current failure codes. |
| `forge.md/11_PHASED_IMPLEMENTATION_PLAN.md` | Links Phase 4 review and keeps Phase 5 separate. |
| `forge.md/12_ARCHITECTURE_DECISIONS.md` | Records the scoped implementation choices and provider/local-effect boundaries. |
| `forge.md/FORGE_FRONTEND_SPEC.md` | Updates the current-scope table/rules for the Phase 4 console extension; future blueprint preserved. |
| `docs/CODE_REVIEW_GUIDE.md` | Reading order, function-versus-tool explanation, walkthrough, and review questions. |
| `docs/PHASE_4_IMPLEMENTATION_REPORT.md` | This report. |

No new package or lockfile dependency was needed. Existing Pydantic/SQLAlchemy/Google SDK and frontend tooling were sufficient. Generated `.next`, package build output, Python/TypeScript caches, and browser screenshots/traces remain ignored artifacts. Earlier runtime-reversal and frontend changes remain uncommitted alongside this work; nothing was reset or pushed.

## 3. Migration and local data

New revision: **0004_tool_hub**, after 0003_initial_runtime. Adds `tools`, `agent_tools`, `tool_calls`, and `demo_tickets`. Existing organizations, agents, immutable versions, and run history are preserved. Tool metadata updates can change status only. A normalized binding cannot introduce an ID absent from the version JSON or from a different organization; updates/deletes/truncation are rejected.

`tool_calls.tool_id` is deliberately nullable for rejected unknown/unbound requests. Valid executed calls always record the exact allowed revision. Tool arguments use JSONB, including safely recorded rejected JSON types; malformed/nonfinite/oversized values are represented by a bounded invalid-payload marker and cannot execute.

The local `forge_local` database was upgraded and checked against ORM metadata. Full downgrade/upgrade tests ran only against disposable `forge_test_utf8`. Browser tests created uniquely named `ui-e2e-…` workspaces and local demo tickets; no pre-existing user workspace/agent/version was modified. The live API and frontend were restarted to load the implementation.

## 4. Tests added and important evidence

New backend tests verify:

- Each of the three demos completes a model/tool/model loop with exact IDs, normalized arguments, ordered events, and two model calls.
- Duplicate run requests return the same run; demo ticket count remains one. Reusing a recorded tool result also keeps one ticket.
- Unknown/unbound tools, extra “authorization” arguments, wrong types, nonfinite JSON, and missing customers do not create a ticket.
- Other organizations cannot read/change tools, bind foreign revisions, or read tool-call evidence. Arbitrary tool registration/code/schema mutations are rejected.
- Disabling a bound tool while the model is responding prevents execution at the Hub's fresh status/policy check.
- A handler that creates a ticket and then returns invalid output, raises an exception, or times out leaves **zero** ticket rows.
- Step and batch caps stop before local side effects.
- Database guards reject tool metadata changes and permission mutation.
- Unknown RUNNING tool outcomes and changed request hashes cannot be automatically replayed; terminal runs cannot initiate new tool calls.
- Gemini declarations/manual function responses preserve the provider call ID and exact opaque signed content; private thought text does not appear in result representation/public evidence. SDK automatic tool execution remains disabled.

Browser tests verify actual registration, cloned permission selections, ticket result inspection, original-version denial, disable confirmation/re-enable, and narrow-screen overflow behavior. Existing workspace, plain-run, archive, lost-response retry, failure/polling, and isolation journeys still pass.

## 5. Commands run

Inspection used `rg`, file reads, Git status, process/port checks, and health requests. Main build/verification commands, from the repository root unless stated:

```sh
FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_test_utf8 .tools/bin/uv run alembic revision --autogenerate -m tool_hub --rev-id 0004_tool_hub
# The generated revision was renamed to 0004_tool_hub.py and reviewed/extended with guards.
.tools/bin/uv run ruff format src tests migrations
.tools/bin/uv run ruff check src tests migrations
FORGE_TEST_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_test_utf8 .tools/bin/uv run pytest -q
FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_local .tools/bin/uv run alembic upgrade head
FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_local .tools/bin/uv run alembic check
.tools/bin/uv pip install --python .tools/production-venv/bin/python --no-deps --reinstall .

# From web/, with Homebrew Node 22 on PATH:
npm run format
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
npm start
```

Local API startup:

```sh
FORGE_ENVIRONMENT=local FORGE_MODEL_BACKEND=fake FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_local .tools/production-venv/bin/uvicorn forge.main:create_app --factory --host 127.0.0.1 --port 8000
```

Development corrections during verification: renamed a registry method that shadowed Python's `list` type; preserved structured duplicate-version errors after binding insertion; adjusted the old timeout assertion to allow elapsed runtime; extended tool timeout to include lock waiting; fixed five-item mobile navigation overflow. Checks were rerun after fixes. No new dependency installation was required.

## 6. Results

| Check | Result |
| --- | --- |
| Python/PostgreSQL suite | **88 passed** |
| Ruff lint/format | Passed |
| Alembic upgrade/downgrade/upgrade on disposable DB | Passed |
| Local migration and metadata agreement | Passed; no pending schema operations |
| Frontend unit/component suite | **14 passed** |
| Playwright browser flows | **5 passed** |
| TypeScript / ESLint / production build | Passed |
| Visual inspection | Tool Hub and tool-run inspector checked; mobile overflow test passed |

The Python suite retains the two pre-existing Starlette/HTTPX and AnyIO deprecation warnings. Playwright's terminal color warning is not a behavior failure. CI workflows were not run remotely and nothing was committed/pushed during this session.

## 7. Limits and unresolved work

- The live backend is **fake**. It makes labelled simulated model requests, while the Tool Hub and local database execution are real. A real Gemini tool round trip has not been tested with a provider key; SDK request/response construction is covered with controlled fixtures.
- Only installed local demo tools are available. No arbitrary tool uploads, remote integrations, real customer data, refunds, messages, or external helpdesk writes were implemented.
- Permission/status/local policy checks are enforced. Business policy revisions, human approval, and PostgreSQL approval continuation remain Phase 5.
- There is no queue, worker recovery, durable provider continuation, cancellation, or outbox. Process/commit failures may leave a visible unfinished run/call. Unknown outcomes are never blindly rerun.
- Local ticket/result atomicity does not establish external side-effect safety. Future integrations need durable downstream idempotency or reconciliation.
- Monetary cost/enforcement and organization-wide rate quotas remain deferred. Call caps and model/handler time limits are implemented; unknown real provider cost stays null.
- A tool disabled after execution was already authorized may finish; disabling blocks subsequent authorization. Registry/version preflight also rejects inactive bindings.
- Legacy draft versions with previously unresolved arbitrary tool UUIDs are preserved and cannot run. Create/clone a new version with valid bindings.
- The current console still lacks organization-wide run listing and production authentication; earlier local-console limits remain applicable.

References for the provider boundary: [Google SDK types](https://googleapis.github.io/python-genai/modules.html), [manual function calling](https://ai.google.dev/gemini-api/docs/generate-content/function-calling), and [signed continuation requirements](https://ai.google.dev/gemini-api/docs/generate-content/thought-signatures). Installed SDK field definitions were also checked locally.

## 8. Recommended next step: review and try Phase 4

Open **http://127.0.0.1:3000/tools**, choose your existing workspace, and register `lookup_customer`. Clone your agent version, give it a new label such as `v2-tools`, check `lookup_customer` under Tool permissions, and save.

In Test version, use this message while the backend is fake:

```text
/tool lookup_customer {"customer_id":"cust_001"}
```

Expected: COMPLETED, fake model label, **2 model calls / 1 tool call**, ALLOW, the pinned tool ID, and Alex Demo's synthetic profile. Try the same request against a version without that permission to see TOOL_NOT_ALLOWED. Tool Hub registration does not change existing versions automatically.

### Follow the functions

```text
Browser button → api.createRun → request → Next proxy → FastAPI create_run
  → RunService.execute: exact version + allowed tool IDs + run idempotency
  → RuntimeEngine.model_step: call FakeAdapter / configured GeminiAdapter
  → model returns function request data
  → ToolHub.execute: validate → permission → persist identity → current policy/limits
  → execute_builtin: lookup synthetic data / write local demo ticket
  → validate output → persist tool evidence
  → ToolExchange → second model call → final reply → terminal run record
  → ToolCallInspector: GET the recorded evidence
```

An ordinary application function call is how our code moves through these layers. A model tool call is a structured request that must pass through the Tool Hub before any handler runs. This distinction is visible side by side in the inspector and explained further in `docs/CODE_REVIEW_GUIDE.md`.

After this review, **Phase 5** is the next stage: deterministic refund policy, human approvals, and persistent pause/resume. It was not started automatically.
