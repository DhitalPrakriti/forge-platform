# Phase 6 — Durability implementation report

## 1. Implemented functionality

Implemented the user-authorized Phase 6 on `dev`, starting from a clean branch. Read the working rules, runtime/security/schema/API/architecture requirements and current FORGE-owned runtime decision before editing. This session does not begin Phase 7.

- **Queued execution by default.** POST /runs commits the run, QUEUED event, schema-2 checkpoint and dispatch intent before returning 202. Provider execution belongs to a separate worker process.
- **Transactional outbox.** PostgreSQL holds one coalesced dispatch row per run, with a generation, due time, publication marker and completion state. It is updated with checkpoints and domain state. Immutable events/checkpoints remain the audit history; the outbox is dispatch state.
- **Redis queue abstraction and locks.** Bounded notifications wake workers; PostgreSQL due-row polling recovers missing notifications. Redis leases renew and release with token-checked scripts. A PostgreSQL session advisory lock on the execution connection prevents concurrent execution even after Redis ownership expires or is lost.
- **Durable MODEL/TOOLS cursor.** Save original model response and private signed continuation, exact model call, tool index/results, prior exchanges, attempt number and step. Reuse saved responses and completed tools after restart.
- **Atomic local-effect recovery.** Installed local demo effect, result, checkpoint and outbox commit together. A killed uncommitted transaction rolls back; its stable RUNNING tool identity can be recovered only through the worker's installed-local/idempotent path. Unknown external tool outcomes remain blocked.
- **Retry/backoff.** Model timeouts/unavailability and interrupted unknown model attempts retry with exponential backoff and jitter. Attempt caps are persisted (default three per model turn). Permanent auth/request/policy/schema failures are not retried. An unknown provider attempt is explicitly recorded and may have incurred charges.
- **Cancellation and deadline enforcement.** A separate durable cancellation record avoids overwriting worker state. Check before/after model work and before tool authorization; already authorized effects can finish. Original runtime includes queue delay, retry delay and approval waiting.
- **Automatic approval continuation and expiry.** A decision commits checkpoint/outbox intent; the worker resumes without another browser action. A pending approval schedules a deadline wake-up and expires without browser activity. Historical Phase 5 explicit resume still works.
- **Safe explicit retry.** Retry creates a new linked run with the same immutable version/input and idempotent request key. A completed or unknown MEDIUM/HIGH-risk effect blocks repetition with RETRY_REQUIRES_RECONCILIATION.
- **Console controls.** Poll queued/retrying states, confirm cancellation, display pending cancellation, retry as a linked run, and distinguish automatic worker continuation from legacy explicit resume.

The current build is `forge-runtime-phase6-v1`; checkpoint schema is 2. Existing versions/runs/schema-1 checkpoints are preserved. Explicit `FORGE_EXECUTION_MODE=inline` keeps the legacy development/test executor and has no Phase 6 recovery guarantee.

## 2. Every changed file and directory

New directory `src/forge/durability/` owns dispatch, ownership, recoverable orchestration and worker controls. Existing runtime/tool/provider boundaries are reused. No new microservice, workflow framework, graph database, or speculative future directories were added.

### New files

| File | Purpose and caller relationship |
| --- | --- |
| `src/forge/durability/__init__.py` | Durability package. |
| `src/forge/durability/models.py` | RunOutbox and RunControl records; used by API control service, checkpoint store and worker. |
| `src/forge/durability/store.py` | `enqueue`, `checkpoint`, `latest`; caller owns commit so dispatch and domain state remain atomic. |
| `src/forge/durability/queue.py` | Queue protocol, Redis notifications, renewable token-owned lease, cleanup. Called by worker. |
| `src/forge/durability/worker.py` | CLI entry point, outbox publisher, due polling, PostgreSQL execution fence, adapter construction. Calls DurableEngine. |
| `src/forge/durability/engine.py` | MODEL/TOOLS cursor, checkpoint compatibility, shared model-call boundary, attempt accounting/backoff, cancellation/deadline, approval continuation, local tool checkpoint callback and terminal evidence. |
| `src/forge/durability/service.py` | API-facing cancellation request and safe linked retry; delegates run creation to RunService. |
| `migrations/versions/0006_durability.py` | Dispatch/control tables, due index and retry parent FK. |
| `tests/test_durability_postgres.py` | 14 PostgreSQL/Redis integration cases, including four real subprocess-kill boundaries. |
| `tests/worker_crash_driver.py` | Test-only subprocess harness pauses at a selected boundary so the parent sends SIGKILL. Never imported by application code. |
| `docs/PHASE_6_IMPLEMENTATION_REPORT.md` | This report. |

### Updated backend/configuration/test files

| File | Change |
| --- | --- |
| `.env.example` | Queue/Redis/model attempt/backoff settings; no real credentials. |
| `.github/workflows/ci.yml` | Disposable Redis service and durability-test environment. |
| `.github/workflows/frontend.yml` | Redis service and actual worker process for queued browser tests. |
| `docker-compose.yml` | Redis and worker services, dependency ordering, shared provider configuration; fake default for demo Compose. |
| `pyproject.toml`, `uv.lock` | Add/pin redis-py 8.0.0; lockfile records exact install. |
| `migrations/env.py` | Registers durability metadata. |
| `src/forge/api/runs.py` | 202 queued creation contract, cancellation and linked retry routes; handlers remain thin. |
| `src/forge/approvals/service.py` | Schema-2 decision checkpoint/outbox, terminal dispatch completion, idempotent queued wake-up; legacy resume retained. |
| `src/forge/core/config.py` | Queued default, Redis URL, worker poll, attempt cap/backoff; empty optional reviewer settings supported for Compose. |
| `src/forge/runtime/models.py` | Nullable retry_of_run_id FK. |
| `src/forge/runtime/schemas.py` | Exposes retry parent in run evidence. |
| `src/forge/runtime/service.py` | Pin execution mode/attempt settings, queued initial checkpoint/outbox, retry source in idempotency hash. Legacy inline branch remains explicit. |
| `src/forge/tools/hub.py` | Worker-only recovery of installed local RUNNING calls; cancellation before authorization; success callback commits checkpoint/outbox with local effect/result. |
| `tests/test_approvals_postgres.py` | Explicit inline setting preserves the earlier Phase 5 compatibility tests. |
| `tests/test_runtime_postgres.py` | Explicit inline setting preserves earlier synchronous runtime tests. |
| `tests/test_postgres.py` | Migration head 0006 and disposable schema agreement/roundtrip. |

### Updated frontend files

| File | Change |
| --- | --- |
| `web/app/api/forge/[...path]/route.ts` | Allow only supported cancel/retry paths in existing proxy. |
| `web/components/approvals/approval-panel.tsx` | Automatic queued continuation copy/confirmation; optional repeat wake-up and legacy explicit resume. |
| `web/components/layout/app-shell.tsx` | Phase 6 scope label. |
| `web/components/runs/run-detail-screen.tsx` | Queue/retry polling, confirmed cancellation and acknowledgement, safe retry key, parent link, mode-aware approval panel. |
| `web/lib/api/forge.ts` | Central cancel/retry requests. |
| `web/lib/api/types.ts` | Optional retry parent for compatibility with older evidence/fixtures. |
| `web/tests/e2e/console.spec.ts` | Await asynchronous completion; automatic approval continuation, linked retry, cancellation confirmation fixture. |

### Updated documentation

- `README.md`, `web/README.md`: worker/Redis startup, queued behavior and current limits.
- `docs/CODE_REVIEW_GUIDE.md`: reading order, caller chain and review questions.
- `forge.md/00_INDEX.md`: report link.
- `forge.md/04_RUNTIME_AND_STATE_MACHINE.md`: durable cursor/ownership/retry/cancel contract.
- `forge.md/05_TOOLS_POLICIES_APPROVALS.md`: auto continuation and scoped local recovery exception.
- `forge.md/07_DATABASE_SCHEMA.md`: actual tables and retry FK.
- `forge.md/08_API_CONTRACT.md`: 202/200/legacy 201, cancel/retry, automatic approval wake-up.
- `forge.md/09_OBSERVABILITY_RELIABILITY_SECURITY.md`: tested reliability boundary and deferred work.
- `forge.md/10_CODEX_WORKING_RULES.md`: records the user's standing instruction to commit/push completed sessions to dev, without automatic main merges or unattended scheduling.
- `forge.md/11_PHASED_IMPLEMENTATION_PLAN.md`: Phase 6 review checkpoint.
- `forge.md/12_ARCHITECTURE_DECISIONS.md`: PostgreSQL dispatch/fencing plus Redis coordination decision.
- `forge.md/FORGE_FRONTEND_SPEC.md`: current worker controls; full dashboard remains future work.

## 3. Migration, dependency and local environment

Migration **0006_durability** follows 0005. Adds `run_outbox`, `run_controls`, and nullable `runs.retry_of_run_id`; no prior migration or immutable historical version is rewritten. The generated revision was reviewed and renamed before application.

The only new application dependency is **redis==8.0.0**, explained before installation. Implementation uses the documented [Redis asyncio client](https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html) and explicit connection cleanup. No Celery, LangGraph, LangChain or separate workflow framework was introduced.

Homebrew Redis 8.10.1 was installed on the Mac and started explicitly on loopback port 56379, without save/AOF or a login service. PostgreSQL remains durable truth. Tests use Redis database 1 with unique prefixes and disposable PostgreSQL `forge_test_utf8`; the local worker uses Redis database 0 and `forge_local` on port 55432. Existing local data was not reset. Local migration/metadata agreement passed.

The API and worker were reinstalled/restarted from the current package; the console was rebuilt. Local fake-mode processes remain available: web 3000, API 8000, Redis 56379, PostgreSQL 55432. The existing ignored `.tools/local-reviewer.env` remains private and unchanged. Generated environments/builds/screenshots are ignored artifacts, not source files for review.

## 4. Tests and evidence

Final verification: **119 backend tests**, **15 frontend unit tests**, and **8 browser flows** pass. Ruff lint/format, TypeScript, ESLint, frontend formatting/build, Alembic disposable roundtrip and local metadata agreement pass. Existing Starlette/HTTPX and AnyIO deprecation warnings remain.

Durability integration tests cover:

- Queued creation and duplicate delivery: one ticket, one tool identity, two model calls.
- Lost Redis notifications and failed publication: PostgreSQL work remains pending and recoverable.
- Token lease loss during active execution: PostgreSQL ownership rejects a second executor.
- Transient retries/backoff and cap; permanent auth errors execute once.
- Cancellation before execution and during model work: no subsequent tool effect.
- Original wall-clock timeout and background approval expiry.
- Approval schedules continuation without a second HTTP resume action.
- Safe linked retry and refusal to repeat a successful ticket after final-model failure.
- Incompatible checkpoint fails visibly before model/tool execution.
- **Real SIGKILL** while model is in flight, after response checkpoint, during uncommitted local effect, and after committed local effect. A fresh worker recovers each run with exactly one ticket. Only the in-flight-model case creates an additional recorded model attempt.

Browser tests use the real local API/worker for queued runs, tool execution, automatic approval, and linked retry. The cancellation presentation test uses an isolated transport fixture; actual cancellation is separately tested against PostgreSQL/Redis. Existing workspace/version/archive/lost-response/scope/error journeys remain covered. Tests were updated where the old UI expected synchronous COMPLETED in the POST response; the new contract correctly returns QUEUED.

Docker is unavailable on this Mac. Compose/workflow YAML was parsed and inspected, but no local Docker build/Compose execution is claimed. CI is configured to run the containers and the queued browser flow after push; remote results are separate from the local results above.

## 5. Commands run

Read-only inspection used rg, Git status/diff, source/spec reads and listener/process checks. Main commands:

```sh
.tools/bin/uv add 'redis==8.0.0'
brew install redis
/opt/homebrew/opt/redis/bin/redis-server --bind 127.0.0.1 --port 56379 --save '' --appendonly no
.tools/bin/uv run ruff check src tests migrations
.tools/bin/uv run ruff format --check src tests migrations
FORGE_TEST_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_test_utf8 FORGE_TEST_REDIS_URL=redis://127.0.0.1:56379/1 .tools/bin/uv run pytest -q
FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_local .tools/bin/uv run alembic upgrade head
FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_local .tools/bin/uv run alembic check
.tools/bin/uv pip install --python .tools/production-venv/bin/python --no-deps --reinstall . redis==8.0.0
# Both backend processes use the same DB, Redis and fake provider environment:
.tools/production-venv/bin/uvicorn forge.main:create_app --factory --host 127.0.0.1 --port 8000
.tools/production-venv/bin/python -m forge.durability.worker
# In web/, with Node 22 on PATH:
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
npm start
```

The local API additionally sources `.tools/local-reviewer.env`; the worker needs no reviewer credential. YAML parsing used Ruby's YAML parser. Dependency/provider references were checked against official Redis documentation. The crash harness exists only in tests; no production crash-switch or secret-bearing debug endpoint was added.

## 6. Limits and unresolved work

- No exactly-once model-provider guarantee. A killed/unknown provider call can be repeated within the cap and can incur extra charges; its original attempt is marked MODEL_OUTCOME_UNKNOWN. Saved responses are reused. Real provider cost remains null until accounting exists.
- Local-effect recovery is based on PostgreSQL atomicity plus the installed local handler/idempotency contract. No payment/helpdesk integration or real money movement was added. Unknown external effects require downstream idempotency or reconciliation.
- Cancellation is cooperative at safe boundaries. A running model call is bounded by its timeout, and an already authorized local tool can finish. Completed effects are not undone.
- Redis/database outages pause new worker acquisition. Committed PostgreSQL state survives; an active PostgreSQL-fenced executor may continue despite Redis lease renewal failure. Catastrophic PostgreSQL data loss is outside these guarantees.
- A worker connection must remain pinned to one PostgreSQL session. Transaction-pooling proxies cannot preserve its session advisory lock.
- Workers execute one run at a time per process and poll batches of due records. Scaling workers is supported by ownership guards; high-throughput scheduling/fairness/load tests are not claimed.
- Legacy inline/schema-1 runs retain their old execution/resume semantics. They are not silently converted into recoverable schema-2 runs.
- Tool execution errors do not receive generic automatic retries; local interrupted transactions can recover safely. Current automatic backoff covers transient model attempts. Dry-run replay is unimplemented.
- Production membership IAM, external integrations, OpenAI adapter/fallback, circuit breakers, monetary budgets, full telemetry and dashboard remain later scoped work. No provider key or live Gemini network call was used.

## 7. Concrete walkthrough and recommended next step

Open http://127.0.0.1:3000. Run your existing tool-enabled version. The browser receives a run ID immediately, then shows worker progress. A normal one-tool fake request ends with two model calls, one tool call, and CHECKPOINT events around its durable boundaries.

For refund review, use the Phase 5 tool/policy bindings and `/tool issue_refund {"customer_id":"cust_001","amount_usd":"425.00"}`. Inspect the exact request, enter the local reviewer credential/reason, and confirm approval. The worker continues automatically. Use a runtime such as 600 seconds for review time; waiting consumes that original limit.

Function/tool flow: `api.createRun` → `RunService.execute` → QUEUED + checkpoint + outbox → `Worker.publish/process` → PostgreSQL fence + Redis lease → `DurableEngine.execute` → shared model adapter → structured tool request → `ToolHub.execute` → local handler → effect/result/checkpoint/outbox commit → next model call → terminal checkpoint. The model requests data; ordinary service functions enforce every permission and recovery decision.

Review in the order in `docs/CODE_REVIEW_GUIDE.md`. Phase 7 (model routing/fallback/accounting) is next but was not started. Publication follows the user's standing dev-branch instruction; the final session response records the actual commit/push result.
