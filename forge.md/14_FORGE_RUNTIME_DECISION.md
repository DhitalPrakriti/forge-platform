# FORGE-Owned Runtime Decision

Status: accepted 2026-09-06. Supersedes the LangChain/LangGraph adoption in specification 13 and architecture decision 7, following the user's explicit reversal request.

## Ownership

FORGE owns a small execution loop and validated run state machine. Keep responsibilities separate: runtime orchestrates, provider adapters call models, Tool Hub validates and executes tools, policy services authorize, approval services persist human decisions. Do not build a general-purpose workflow framework or speculative adapter system.

PostgreSQL remains durable truth. FORGE manages continuation state in `run_checkpoints` through SQLAlchemy/Alembic. Redis remains coordination/cache, and queue/workers arrive in Phase 6. No graph database, LangChain, LangGraph, vendor checkpointer tables, graph thread IDs, or additional checkpoint driver is required for V1.

## Planned execution path

```text
API → resolve exact version → persist run → FORGE runtime → provider adapter
                                              ↓ tool request
                                          Tool Hub validation
                                              ↓ policy
                                  deny / require approval / allow
                                              ↓
                                    checkpoint → continue / finish
```

Before high-impact execution, persist a stable tool-call identity and enforce schema, permissions, policy, budget, and approval requirements. A model response never grants authorization.

For durable transitions, write run state, state version, checkpoint, events, and outbox intent in one PostgreSQL transaction. Queue publication follows through the outbox. Provider calls and external tool effects cannot share that transaction; downstream idempotency or outcome reconciliation remains necessary. Never automatically repeat an irreversible action with an unknown outcome.

An approval pause stores its normalized request hash and continuation state. An authenticated decision records resume intent. Resume loads the same run, checks compatibility, cancellation/deadline, approval expiry, policy and limits, then continues. Retry/replay semantics remain as specified in document 12. Persist checkpoint schema and runtime build versions; reject incompatible recovery visibly.

## Implementation phases

| Phase | Scope |
| --- | --- |
| 3 | In-process FORGE execution, exact-version runs/events, Gemini adapter, model-call persistence, fake-model tests |
| 4 | Tool Hub schemas, registry, demo tools, recorded calls |
| 5 | Deterministic policy, approvals, durable PostgreSQL continuation and pause/resume |
| 6 | Queue/workers, Redis locks, outbox delivery, full checkpoint recovery, idempotency, retry/timeout/cancellation and crash tests |
| 7 | OpenAI adapter, fallback, provider health, circuit breaker and cost accounting |

Explain provider/queue dependencies before adding them and pin compatible versions when implemented. Phase 3 makes no crash-recovery guarantee before the relevant persistence work. LangGraph could later be evaluated as an adapter if a concrete need appears; it is not scheduled or implemented by this decision.

## Existing implementation and review

Phase 1/2 code requires no rollback: framework execution has not been implemented and no framework packages are installed. Existing immutable runtime template labels remain valid framework-neutral identifiers. No migration is added or edited for this decision.

Keep the session file/directory map, reading order, request walkthrough, commands/results, and review questions required by working rules. Historical adoption/session reports remain records of past decisions; their framework directions are superseded by this document.
