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

Persist FORGE state transitions, domain events, and enqueue intent atomically in PostgreSQL using the outbox pattern. LangGraph owns graph checkpoints in separate transactions; reconcile the two stores idempotently. A shared PostgreSQL server does not make these writes one atomic transaction. This supersedes the original combined checkpoint transaction proposal. Redis locks supplement database concurrency checks; they are not durable truth. Workers recover without relying on Redis history.

Before irreversible execution persist the tool-call identity and stable idempotency key. The downstream integration must durably deduplicate that key or provide reliable outcome reconciliation. A crash after the side effect but before result persistence must be resolved through that mechanism. An unknown outcome without reconciliation fails visibly and must not be retried automatically. A stored result alone cannot close this crash window.

## 5. No V1 gate overrides

A failing or missing release decision blocks production promotion. Remove override fields from the V1 schema. Rollback can restore a previously deployed known-good version in the same agent/environment without evaluating it as a new candidate; preserve its original release evidence and audit the rollback. Automatic rollback and canaries remain future work.

## 6. Phase 1 scope and tooling

Python 3.12, FastAPI/Uvicorn, Pydantic Settings, SQLAlchemy 2.x async with asyncpg, Alembic, PostgreSQL 16, pytest/HTTPX, Ruff, Docker Compose, and GitHub Actions. uv provides Python/environment management and a committed dependency lock. Hatchling builds the Python package. These supporting dependencies enable the prescribed stack.

Configuration requires an explicit database URL; checked-in credentials are local/CI examples only. Database URLs are secret values in settings. API startup creates and shutdown disposes the connection pool. Liveness is independent of the database; readiness runs a bounded query. Schema migration is a separate deployment step. The initial empty revision establishes Alembic history without implementing Phase 2 tables. Request errors use the specified envelope and never include raw validation inputs or internal exception strings.

No agents, organizations, runtime, queue, provider adapters, authentication system, evaluation, deployment domain, or dashboard are implemented in Phase 1. Their earlier specification decisions are documentation only.

## 7. Adopt LangChain and LangGraph

Accepted following the user's request to use the LangChain ecosystem, reduce custom pipeline code, and make session reviews easier. LangChain `create_agent` is the default loop; LangGraph is the execution/checkpoint/interrupt engine. FORGE retains deterministic platform services. Remove the planned custom checkpoint store and separate workflow engine. Details and official references are in `13_LANGCHAIN_LANGGRAPH_RUNTIME.md`.

Phase 1 code remains valid. Add framework dependencies only with the phase that uses them, explain each dependency first, and pin compatible versions. Every session supplies a file/directory review map and updates the persistent review guide when the structure changes.

## 8. Phase 2 access and lifecycle boundaries

Phase 2 registry implementation uses development organization selection and fails closed in production until membership authentication is implemented. This is not production IAM. Draft versions preserve typed configuration and reference intent, with PostgreSQL immutability guards. Staging cannot succeed before model/tool/policy/evaluation reference validation exists. The concrete request and lifecycle contracts are in `03_AGENT_DEFINITION_AND_REGISTRY.md` and `08_API_CONTRACT.md`. No new runtime dependency is introduced in this phase.
