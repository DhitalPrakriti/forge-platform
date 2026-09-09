# Runtime and State Machine

## Execution Engine

FORGE implements the execution loop and validates run-state transitions. PostgreSQL holds durable state. Ownership and phased recovery requirements are in `14_FORGE_RUNTIME_DECISION.md`.

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

FORGE owns checkpoint scheduling and storage. Persist progress after:

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

## Runtime Integration Rules

Use FORGE `run_checkpoints` for durable execution and approval resume. Resume the same run from a compatible checkpoint; explicit retry/replay creates a new linked run. Persist checkpoint schema, runtime template, and build versions. Bound retries and coordinate provider attempts with queue redelivery.

Persist approval requests and waiting state before returning control. The approval service commits an authenticated decision and resume intent; runtime revalidates the exact request, expiry, cancellation, and remaining limits before execution. Persist checkpoint, state version, domain events, and outbox intent in one transaction where they describe the same transition. External effects remain outside that transaction and require downstream idempotency or reconciliation.

## Phase 3 Implemented Execution Contract

Phase 3 adds development-only `POST /runs` for an exact DRAFT/STAGING version of an active agent. This is an initial runtime testing endpoint, not a production deployment alias or the full Phase 9 Playground. It executes one model call in-process. The valid synchronous path is `CREATED → RUNNING → COMPLETED/FAILED/TIMED_OUT`; no queue is simulated. Current step/model-call count is one, within validated max_steps. Tools, policies, fallback configurations, and unknown runtime template revisions are rejected before execution. Staging/release lifecycle remains unchanged.

A required organization-scoped Idempotency-Key binds the normalized version/input hash. Same key/input returns the persisted run (including an in-progress or failed run) without another model call; changed input returns 409. Run creation/RUNNING event/model-call intent commit before the external call. Final model-call evidence and terminal run/event commit together. SQLAlchemy optimistic state_version updates detect stale writers. Events use state_version as their unique per-run sequence, starting at zero.

The wait for a provider result is bounded by the smaller of the configured model timeout and version runtime limit. SDK automatic retries and tool execution are disabled. Unexpected tool calls are rejected without execution; incomplete/blocked responses do not become successful answers. Full wall-clock enforcement, cancellation, checkpoints, process-crash recovery and queue redelivery remain later-phase work. If the process or final database write fails after provider invocation, the recorded run may remain RUNNING; duplicate requests must not automatically reissue it.

Fake mode is an explicitly configured development backend, identified in output and persisted provider metadata. Gemini mode requires a server-side key and records requested/actual model, SDK version, available token usage and latency. No provider key is present in prompts, request/response schemas, run configuration or events. Dollar-cost estimation and enforcement of budget_config are not implemented until Phase 7: real cost fields are null, and execution_config declares this limitation. Fake calls have known zero external cost. No production runtime route is enabled before authentication and release/deployment controls exist.

## Phase 4 execution extension

Phase 3 above records the original single-call milestone. Phase 4 extends `standard-agent-v1` with an in-process model → Tool Hub → model loop. Exact registered tool bindings are supported; policy bindings and fallbacks remain rejected. Runtime build identity is `forge-runtime-phase4-v1`. Existing saved runs retain their original build/configuration.

`max_steps` bounds model turns. A tool request needs a remaining model turn for its final response; otherwise STEP_LIMIT_EXCEEDED fails before the tool side effect. Tool calls run serially, capped at eight per model response and 32 per run. `tool_calls_count` counts recorded attempts, including denials. `current_step`/`model_calls_count` count model turns, not tool calls.

Model-call intent commits before each provider request. A tool response transitions RUNNING → WAITING_FOR_TOOL; each call records request and completion events, then successful calls transition back to RUNNING. State transitions and domain evidence use the same monotonic state_version/event sequence. Text-only runs keep the original three-event path.

Time remaining is recomputed before model turns and tool execution; handler time and tool-lock waiting are bounded. Database availability/commit failures and process recovery remain durability concerns. The engine retains provider continuation data only in memory. Gemini function IDs and original signed content are sent back to Gemini as required, but hidden thought text and opaque signatures are not included in API records, logs, or tool evidence. SDK automatic function execution remains disabled.

Tool validation/permission/output errors fail visibly. Tool/run timeouts end TIMED_OUT. No checkpoint, approval resume, cancellation, retry worker, queue, or crash-recovery claim is added. Monetary enforcement is declared `DEFERRED_TO_PHASE_7` in new execution_config records.

## Phase 5 approval continuation

WAITING_FOR_TOOL may transition to WAITING_FOR_APPROVAL. The waiting call, approval, checkpoint, event, and run state commit atomically. After a saved human decision, explicit resume claims the run as RUNNING and re-enters the saved tool batch. Completed calls are reused; the pending call verifies exact approval before execution. Multiple approval pauses retain earlier exchanges. No previous model turn is repeated. Checkpoint serialization preserves private provider content, schema/build versions, and original execution limits. Queue-based recovery remains Phase 6.
