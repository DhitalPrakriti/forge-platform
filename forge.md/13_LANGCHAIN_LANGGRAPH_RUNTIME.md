# LangChain and LangGraph Runtime

Status: accepted architecture; framework implementation starts in Phase 3. Phase 1 remains the HTTP/database foundation.

## Default approach

Use LangChain `create_agent`, which runs on LangGraph, for the standard model/tool loop. Configure it from an immutable FORGE agent version. Use LangChain model integrations, message types, tool interfaces, and middleware. Keep provider adapters thin. Use explicit LangGraph `StateGraph` composition only if a concrete requirement cannot be expressed clearly through the standard API; document that reason before implementation.

This avoids implementing a manual model/tool loop while keeping FORGE-specific policy and release logic visible. FORGE still requires application code for its platform responsibilities.

## Ownership

| Concern | Owner |
| --- | --- |
| Standard agent loop and model/tool interfaces | LangChain |
| Graph execution, graph state, checkpoints, interrupt/resume | LangGraph |
| Agent/version/deployment identity and public run status | FORGE services and PostgreSQL domain tables |
| Tool permission, validation, policy, budgets, approval decisions | FORGE services invoked through LangChain middleware/wrappers |
| External action idempotency and outcome reconciliation | FORGE tool integration and downstream provider |
| Worker delivery, locks, outbox, cancellation/deadlines | FORGE execution service |
| Evaluation evidence, release gates, promotion, rollback | FORGE |

The public run status enum is not a second scheduler. The runtime integration maps framework progress to those domain statuses and validates updates.

## Planned request path

```text
API → FORGE run service → pinned version → LangChain create_agent / LangGraph
                                             ↓ model integration
                                             ↓ FORGE guarded tool invocation
                                                  ├ deny
                                                  ├ persist approval → interrupt
                                                  └ execute with idempotency
FORGE approval service → authenticated decision → Command(resume=...) → same thread
```

The API remains thin. Queue/worker delivery arrives in Phase 6. Framework objects belong inside `runtime/` and thin model/tool integration modules, not API request schemas.

## Persistence and consistency

- One FORGE run maps to one server-generated LangGraph `thread_id`. Resume uses the same thread; explicit new retry/replay runs use new threads. A thread ID alone grants no access: every operation first checks organization/run ownership.
- Use the official PostgreSQL async checkpointer for durable graph state. Do not introduce a separate `run_checkpoints.runtime_state` table.
- SQLAlchemy/Alembic manages FORGE domain tables. The pinned checkpointer package manages its own tables/setup migrations. Run its setup explicitly during deployment; test upgrades before changing package versions. Do not invoke setup on every request or recreate vendor tables in Alembic.
- Keep the existing asyncpg domain engine. The official PostgreSQL checkpointer uses its supported driver/pool (currently psycopg); introduce this separate infrastructure dependency in Phase 5, with an explanation and a lockfile update. Do not rewrite FORGE's ORM to share a driver.
- Graph checkpoints and domain transactions are separate. Commit domain status/events/outbox atomically, and use stable operation IDs to reconcile checkpoints with domain evidence after crashes. Never claim atomicity merely because both use PostgreSQL.
- Before each side effect, persist its stable call identity and consult the authoritative tool/approval record. If checkpoint recovery re-enters an already completed operation, return its stored result. Uncertain downstream outcomes still require idempotency/reconciliation; framework persistence is not an exactly-once external-action guarantee.
- Recovery must handle domain writes before a checkpoint, a checkpoint before the public status update, and an approval decision before the graph is durably interrupted. Reconcile these gaps before accepting the corresponding phase.
- Pin runtime template/build and framework versions for historical runs. Resume only with compatible code; reject incompatible recovery visibly rather than silently migrating live graph state.

## Approval, retry, and limits

Use `interrupt()` to pause and `Command(resume=...)` to continue after the FORGE approval service commits an authenticated decision. Interrupted nodes restart on resume. Pre-interrupt database writes must be idempotent, and irreversible tools execute only after authoritative approval revalidation. Never treat a boolean supplied by an API client as approval authority.

Interrupts may wait indefinitely; FORGE enforces approval expiry and run deadlines. Recheck cancellation/deadline/approval before any resumed side effect. Process side-effecting tool calls serially in V1.

Use framework retry mechanisms with deterministic transient-error classification and bounded attempts. Coordinate model integration retries, graph retries, and queue redelivery so they do not multiply invisibly. Record actual attempts and costs. Domain policy denials, invalid arguments, and expired approvals are not transient failures.

Do not swallow framework interrupt/control-flow signals in broad exception handling inside agent nodes/middleware. FORGE's HTTP error boundary remains separate.

## Dependencies by phase

| Phase | Planned packages and use |
| --- | --- |
| 3 | `langchain`, `langgraph`, Gemini integration (`langchain-google-genai`); standard loop, messages, model calls |
| 4 | Existing LangChain tool interfaces; add no unrelated integration bundles |
| 5 | `langgraph-checkpoint-postgres` and supported psycopg pool dependencies; durable approval resume |
| 6 | Queue/Redis packages selected for distributed execution; reuse framework persistence |
| 7 | `langchain-openai`; fallback provider integration |

Check current compatibility and pin versions when implementing each phase. These packages are not installed by this documentation change. Hosted LangSmith tracing/platform services are not required or automatically enabled. FORGE's specified evaluation and OpenTelemetry work remain in scope for later phases.

## Review and acceptance

Use deterministic fake models/tools for normal tests. Add integration coverage at the owning phase for model/tool routing, guarded calls, interrupt/restart/resume, cross-organization rejection, checkpoint/domain reconciliation, expired approvals, duplicate delivery, cancellation, and uncertain side-effect outcomes. Do not replace these with tests of framework internals.

Every session includes a directory/file map, a concrete execution walkthrough, exact commands/results, and limitations. See `../docs/CODE_REVIEW_GUIDE.md`.

## Official references

- [LangChain agents](https://docs.langchain.com/oss/python/langchain/agents): standard agent construction and extension points.
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview): execution framework responsibilities.
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence): thread-scoped graph checkpoints.
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts): pause/resume and node restart behavior.
- [PostgreSQL persistence setup](https://docs.langchain.com/oss/python/langgraph/add-memory): persistent saver and supported driver setup.

Ownership and phase choices above are FORGE architecture decisions informed by these references.
