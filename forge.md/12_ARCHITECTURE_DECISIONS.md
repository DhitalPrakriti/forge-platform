# FORGE Architecture Decisions

Status: accepted for V1 following the request to resolve specification ambiguities.

## 1. Immutable configuration, mutable lifecycle metadata

Agent-version instructions, model configuration, runtime/budget limits, and dependency bindings never change after creation. Lifecycle metadata can change through validated service operations. Failed evaluation returns a candidate to STAGING; a corrected configuration requires a new version. Deployment pointers determine active traffic; lifecycle labels alone do not route requests. Detailed allowed transitions belong to the registry implementation.

## 2. One deployment authority

`deployments.agent_version_id` is the sole pointer for `(agent, environment)`. Remove `agents.active_production_version_id` from the planned schema. Promotion/rollback updates the pointer, history, and audit in one PostgreSQL transaction with concurrency control. New runs atomically resolve and persist the chosen version; existing runs keep their original version. Every lookup enforces organization ownership.

## 3. Pin dependencies, preserve evidence

Agent versions bind immutable tool revisions, policy revisions, model configuration, and evaluation-suite revisions. Tool administrative status can change, but handler/schema changes require a new revision. Evaluation runs preserve case inputs, evaluator versions, judge configuration, baseline evaluation ID, metrics, and gate revision. Model calls retain requested and actual provider/model identifiers and any available provider revision metadata. Provider aliases may change remotely, so FORGE promises configuration/evidence reproducibility, not identical LLM outputs. Production gate evidence must apply to the exact candidate, gate revision, and baseline; changed baselines require a new release check. First deployment uses absolute gates without a production baseline.

## 4. Recovery and explicit new executions

Terminal runs remain terminal. Automatic transient retries occur within a nonterminal run with bounded retry count/backoff. Explicit `/retry` creates a new linked run for FAILED or TIMED_OUT runs, with the same immutable version/input and fresh approvals; it never repeats a successful irreversible action automatically. `/replay` creates a new linked DRY_RUN execution from any terminal run, using recorded tool results/mocks; missing recordings must not trigger live side effects. Both operations require request idempotency. Their persistence fields arrive with runtime implementation.

Cancellation and timeout may terminate any nonterminal state. Approval denial or expiry cancels a waiting run in V1. Approval decision/expiry races are serialized in PostgreSQL. A resume revalidates the exact request binding, unexpired approval, pinned policy/permissions, and limits. Approval waiting counts toward the configured wall-clock runtime limit.

Persist FORGE state transitions, checkpoints, domain events, and enqueue intent in the same PostgreSQL transaction for each durable transition. Use the transactional outbox for queue delivery. External provider/tool effects are outside the transaction and still need idempotency/reconciliation. This restores FORGE checkpoint ownership following the reversal in decision 9. Redis locks supplement database concurrency checks; they are not durable truth. Workers recover without relying on Redis history.

Before irreversible execution persist the tool-call identity and stable idempotency key. The downstream integration must durably deduplicate that key or provide reliable outcome reconciliation. A crash after the side effect but before result persistence must be resolved through that mechanism. An unknown outcome without reconciliation fails visibly and must not be retried automatically. A stored result alone cannot close this crash window.

## 5. No V1 gate overrides

A failing or missing release decision blocks production promotion. Remove override fields from the V1 schema. Rollback can restore a previously deployed known-good version in the same agent/environment without evaluating it as a new candidate; preserve its original release evidence and audit the rollback. Automatic rollback and canaries remain future work.

## 6. Phase 1 scope and tooling

Python 3.12, FastAPI/Uvicorn, Pydantic Settings, SQLAlchemy 2.x async with asyncpg, Alembic, PostgreSQL 16, pytest/HTTPX, Ruff, Docker Compose, and GitHub Actions. uv provides Python/environment management and a committed dependency lock. Hatchling builds the Python package. These supporting dependencies enable the prescribed stack.

Configuration requires an explicit database URL; checked-in credentials are local/CI examples only. Database URLs are secret values in settings. API startup creates and shutdown disposes the connection pool. Liveness is independent of the database; readiness runs a bounded query. Schema migration is a separate deployment step. The initial empty revision establishes Alembic history without implementing Phase 2 tables. Request errors use the specified envelope and never include raw validation inputs or internal exception strings.

No agents, organizations, runtime, queue, provider adapters, authentication system, evaluation, deployment domain, or dashboard are implemented in Phase 1. Their earlier specification decisions are documentation only.

## 7. Adopt LangChain and LangGraph — superseded

Previously accepted to reduce custom execution code. Reversed at the user's request on 2026-09-06; see decision 9 and `14_FORGE_RUNTIME_DECISION.md`. The original proposal remains in `13_LANGCHAIN_LANGGRAPH_RUNTIME.md` as historical context only. Session code-review requirements remain active.

## 8. Phase 2 access and lifecycle boundaries

Phase 2 registry implementation uses development organization selection and fails closed in production until membership authentication is implemented. This is not production IAM. Draft versions preserve typed configuration and reference intent, with PostgreSQL immutability guards. Staging cannot succeed before model/tool/policy/evaluation reference validation exists. The concrete request and lifecycle contracts are in `03_AGENT_DEFINITION_AND_REGISTRY.md` and `08_API_CONTRACT.md`. No new runtime dependency is introduced in this phase.

## 9. Restore FORGE-owned runtime

Accepted 2026-09-06 at the user's explicit request to reverse LangGraph adoption. FORGE owns the V1 execution loop/state machine, PostgreSQL checkpoints, and approval continuation. Provider SDKs sit behind adapters. LangChain/LangGraph are not mandatory dependencies; a future adapter requires a new scoped decision. No graph database is required. Existing Phase 1/2 code and immutable runtime template labels stay unchanged because framework execution was never implemented. See `14_FORGE_RUNTIME_DECISION.md`.

## 10. Phase 4 local Tool Hub slice

Following the request to continue to the next stage, implement Tool Hub with the three prescribed installed demo tools and the minimum console controls needed to test them. The registry does not accept executable code, remote URLs, or client-defined schemas. Existing Pydantic models generate schemas and perform strict validation; no new runtime dependency is required.

New immutable versions pin valid same-organization tool revisions in both their JSON configuration and `agent_tools`. Historical unresolved draft intent remains unchanged and cannot execute. Tool schemas/handlers/risk metadata are immutable; an ACTIVE/INACTIVE switch can block subsequent execution. A model request does not authorize a tool. The local-only deterministic allowlist is the Phase 4 policy boundary; business policies, high-impact tools, and human approvals remain Phase 5.

Record denied requests even without an allowed tool ID, hence nullable `tool_calls.tool_id`. Each request gets stable identity before execution. Demo ticket writes, validated results, and completion evidence share a database transaction; savepoint rollback prevents a failed/invalid output from retaining the local write. This does not solve external integration crash windows or provide worker recovery.

Keep the provider adapter boundary: Gemini SDK automatic execution remains disabled, function response IDs and signed content are preserved in transient history, and no hidden thought content is exposed as run evidence. The fake adapter uses explicit `/tool` commands solely to demonstrate the same Tool Hub pipeline without a provider key.

## 11. Phase 5 local approval continuation

Accepted for this implementation session: immutable installed refund policy, local simulated refunds, authenticated local reviewer with a server-owned UUID, and private PostgreSQL checkpoints. No dependency was added. Review credentials are local operator access, not production organization membership; the production guard remains enforced.

Approval commits resume intent as an event. Explicit authenticated in-process resume is used until Phase 6 introduces queue/outbox workers. Claiming a waiting run is serialized in PostgreSQL. Recovery is supported across approval pauses, not arbitrary crashes after execution claims. Exact Gemini content/signatures are privately serialized for continuation, with schema/build/SDK compatibility checked before resume. No checkpoint contents are exposed as public trace evidence. Preserve original deadlines while waiting; expiry is processed on decision/resume until a worker sweeper exists.

## 12. Phase 6 durable dispatch and worker ownership

PostgreSQL provides coalesced dispatch intent and immutable checkpoint history. Redis carries disposable notifications and renewable run leases. Workers poll due database intents as a loss-recovery path. A PostgreSQL session advisory lock is held on the execution connection across its transactions, so Redis lease loss cannot permit concurrent execution. This remains one modular monolith with a separate worker entry point, not a new microservice.

Schema-2 MODEL/TOOLS cursors reuse the existing provider adapters, signed continuation codec, and Tool Hub. The legacy inline path remains explicit for historical development tests; queued mode is the default. Local tool effects/results/cursor/outbox commit atomically, permitting safe same-key recovery of installed local handlers. Unknown model attempts can retry within a persisted cap, with uncertain provider usage retained. Unknown external side effects are never blindly replayed. Approval decisions enqueue automatically, expiry is scheduled in PostgreSQL, and cancellation uses a separate durable control record to avoid overwriting a worker's state.
