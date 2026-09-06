# Runtime and State Machine

## Execution Engine

Use LangChain `create_agent` on LangGraph for the agent loop. FORGE validates public run-state transitions; these statuses are an operational projection, not another graph scheduler. Framework details and recovery rules are in `13_LANGCHAIN_LANGGRAPH_RUNTIME.md`.

## Runtime Responsibilities

- load version;
- create/continue run;
- call model router;
- process tool requests;
- enforce limits;
- checkpoint;
- pause/resume;
- cancel;
- retry;
- timeout;
- complete/fail.

## Run States

```text
CREATED
QUEUED
RUNNING
WAITING_FOR_TOOL
WAITING_FOR_APPROVAL
RETRYING
COMPLETED
FAILED
CANCELLED
TIMED_OUT
```

## State Machine

```text
CREATED → QUEUED → RUNNING
                    ├→ WAITING_FOR_TOOL → RUNNING
                    ├→ WAITING_FOR_APPROVAL → RUNNING/CANCELLED
                    ├→ RETRYING → RUNNING
                    ├→ COMPLETED
                    ├→ FAILED
                    ├→ TIMED_OUT
                    └→ CANCELLED
```

Invalid transitions are domain errors.

## Durable Execution

Without durability:

```text
step 1 ✓
step 2 ✓
server crash
→ restart everything
```

With FORGE:

```text
step 1 ✓
step 2 ✓
checkpoint
server crash
→ reload checkpoint
→ continue step 3
```

## Checkpoint Boundaries

LangGraph owns checkpoint scheduling and storage. Structure graph steps/middleware so durable progress covers:

- model response;
- successful tool execution;
- approval request;
- approval decision;
- retry decision;
- terminal state.

## Idempotency

Irreversible tools use stable idempotency keys:

```text
forge:{run_id}:{tool_call_id}
```

If duplicate queue delivery occurs and the tool call already succeeded, FORGE reuses the stored result instead of executing again.

## Concurrency

Use one run lock:

```text
forge:run:{run_id}
```

and optimistic `state_version` updates to protect against races.

## Retry Classification

Retry transient:

```text
429
500/502/503
network timeout
provider temporarily unavailable
```

Do not retry:

```text
policy denial
invalid arguments
auth failure
budget exceeded
permanent 4xx
```

Use exponential backoff + jitter.

## Retry, Replay, and Recovery Semantics

See `12_ARCHITECTURE_DECISIONS.md` for terminal-state behavior, explicit retry/replay semantics, approval expiry, transactional outbox delivery, and uncertain external tool outcomes. The state diagram above shows the main path, not the complete transition matrix.

## Framework Integration Rules

Use the PostgreSQL checkpointer for durable execution and approval resume. One FORGE run maps to one server-generated LangGraph thread; a new retry/replay run gets a new thread. Persist graph/template and runtime build versions. Use framework retry support with FORGE's error classification and bounds; coordinate provider retries to avoid multiplying attempts.

Approval uses `interrupt()` / `Command(resume=...)` behind the FORGE approval service. Resume may re-execute node code; writes before an interrupt must be idempotent. FORGE timeout/expiry remains enforced because an interrupt itself can wait indefinitely. Do not catch and suppress framework interrupt signals in generic node error handling.

No custom `run_checkpoints.runtime_state` store is created. FORGE status/events/outbox are committed together; framework checkpoint commits are separate and require idempotent reconciliation as described in the runtime guide.
