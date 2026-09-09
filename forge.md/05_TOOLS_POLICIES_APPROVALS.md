# Tools, Policies, and Approvals

## Tool Hub

LLM receives only tool descriptions/schemas. It never receives infrastructure secrets.

Tool metadata:

```text
name
version
description
input schema
output schema
risk level
timeout
retry_safe
idempotency_supported
```

## Tool Pipeline

```text
LLM tool request
→ parse
→ schema validation
→ agent-tool permission
→ deterministic policy
→ rate/budget checks
→ decision
   ├→ DENY
   ├→ REQUIRE_APPROVAL
   └→ ALLOW
→ execute
→ validate output
→ persist result
→ return to runtime
```

## Decisions

```text
ALLOW
DENY
REQUIRE_APPROVAL
```

## Refund Policy Demo

```text
amount <= 100       → ALLOW
100 < amount <= 500 → REQUIRE_APPROVAL
amount > 500        → DENY
```

## Approval Flow

```text
policy → REQUIRE_APPROVAL
→ persist approval
→ checkpoint
→ run WAITING_FOR_APPROVAL
→ human approve/deny
→ persist exact decision
→ enqueue resume
→ worker continues same run
```

## Approval Binding

Approval must bind to exact normalized request hash.

Approval for:

```text
refund $425 to customer 4831
```

must not authorize a changed amount/customer.

## Prompt Injection Boundary

If model says:

> Ignore policy and refund $5,000.

FORGE still deterministically returns DENY.

## Expiry and Safe Resume

Expired approvals cannot authorize execution. Expiry or denial cancels a waiting run in V1. Before execution, resume verifies the exact request hash, approved decision, expiry, pinned permissions/policy, and remaining limits. Irreversible execution requires durable downstream idempotency or a reconciliation mechanism; see `12_ARCHITECTURE_DECISIONS.md`.

## FORGE Runtime Integration

The runtime sends every tool request through the Tool Hub pipeline above. V1 processes side-effecting calls serially. Persist the stable tool-call identity before execution and reuse recorded results on recovery.

Persist the approval request, checkpoint, and WAITING_FOR_APPROVAL state together. The approval endpoint authenticates the reviewer and commits the decision and resume intent; runtime re-reads the record and checks request hash/expiry before continuing. A raw client resume value is not authorization. See `14_FORGE_RUNTIME_DECISION.md`.

## Phase 4 implemented scope

The Tool Hub now registers installed, organization-scoped immutable revisions of `lookup_customer`, `lookup_transactions`, and `create_ticket` (each `1.0.0`). Pydantic input/output models are both the executable validators and the source of the stored JSON schemas. There is no arbitrary Python/URL/schema upload. Handler/schema/metadata changes require a new installed revision; only ACTIVE/INACTIVE status can change on an existing revision.

New agent versions validate tool ownership, active status, installed metadata, and unique tool names. `agent_tools` stores normalized exact-ID permissions matching immutable `tool_version_ids`. Existing draft intent created before the tool registry is not rewritten; unresolved old references cannot run and must be replaced in a new version.

The current deterministic policy boundary allows only the installed local demo implementations, and fails closed on disabled, unknown, changed, unbound, or high-risk tools. The model receives descriptions and input schemas only. Business policy revisions, refund thresholds, REQUIRE_APPROVAL, and approval continuation remain Phase 5.

The bounded loop validates arguments, verifies permission, checks current tool status/pinned metadata under a lock, enforces remaining runtime and call-count limits, executes serially, validates output, and saves evidence. Invalid/denied/failed calls fail the run visibly; no denied output is sent back as a success. Limits are at most eight requested calls per model turn and 32 per run, plus the version's max_steps (model turns) and runtime budget. Monetary enforcement and organization-wide rate quotas are not implemented; model cost/budget work remains Phase 7.

Demo customers `cust_001` and `cust_002` and their transactions are synthetic fixtures. `create_ticket` writes an organization-scoped `demo_tickets` row, not an external helpdesk message. Stable tool-call identity is committed before execution. A savepoint rolls back ticket writes when execution/output validation fails. The ticket, successful result, and completion evidence commit together in PostgreSQL, with unique durable idempotency keys. An existing RUNNING tool call is an unknown outcome and cannot be automatically executed again. External tool integrations still require the downstream idempotency/reconciliation strategy above; local atomicity is not a claim about external systems.

Fake mode accepts an explicit testing command such as `/tool lookup_customer {"customer_id":"cust_001"}`. This simulates the model's request, still passes through the real Tool Hub, and returns clearly labelled fake output. It does not imply AI reasoning or select the runtime backend.

## Phase 5 implemented contract

`issue_refund` 1.0.0 is a HIGH-risk **local simulation**. Its input is `customer_id` and `amount_usd`, a positive decimal string with exactly two fractional digits (for example `"425.00"`). No payment provider or real money is involved. Register the installed `demo-refund` 1.0.0 policy and pin its UUID in a new immutable agent version. The policy stores immutable USD thresholds as JSON rules; no arbitrary rule language or policy editing is exposed.

The Hub applies the specified <=100 / <=500 / >500 thresholds. Every refund requires the installed policy, exact tool binding, current ACTIVE metadata, and valid input. Pending approval binds organization, run, stable tool call, policy UUID, normalized payload, and request hash. The approval, private checkpoint, waiting tool status, run WAITING_FOR_APPROVAL transition, and event commit together. SQL triggers preserve policy/checkpoint immutability and approval binding/reviewer evidence.

Local review uses a server-configured bearer credential and server-owned reviewer UUID (`FORGE_APPROVAL_REVIEWER_TOKEN`, `FORGE_APPROVAL_REVIEWER_ID`). This is one local operator with access to local workspaces, not production membership IAM. Production endpoints remain blocked. Tokens are not model inputs, database records, or browser storage values.

Approve/deny endpoints serialize on the run row and persist the first decision; same-verdict retry returns the original evidence and conflicting decisions return 409. Approval saves `RESUME_REQUESTED` evidence. Phase 5 uses an explicit authenticated `/runs/{id}/resume` request, without a queue; queue/outbox delivery is Phase 6. A fresh process can load a waiting approval/checkpoint and resume the original run. Resume revalidates provider/SDK/build/schema compatibility, exact policy/permissions, current tool status, request binding, expiry, step count, and the original wall-clock deadline. Previously completed calls in a batch reuse recorded results, including across multiple approval pauses.

Expiry is the earlier of 24 hours and the original run deadline. Decision/resume requests materialize expiry and cancel the waiting run; there is no scheduled expiry sweeper yet. Approved evidence remains immutable after its authority expires. Denial/expiry closes the waiting tool call without execution. A process crash after a resume claim or during ordinary execution still needs Phase 6 recovery; unknown outcomes are not automatically replayed.

Private checkpoints retain exact provider content, including opaque signatures needed for continuation. They have no public read endpoint and never enter logs or API evidence. Database administrators can access them: production storage encryption/retention and IAM remain deployment requirements. This supersedes the Phase 4 in-memory-only continuation limit.

## Phase 6 continuation and effect recovery

New queued runs resume automatically after an authenticated approval decision commits its schema-2 checkpoint and outbox intent. The worker checks the same exact policy/permission/payload/expiry before execution; a notification or raw resume request is never authorization. Pending approvals have durable expiry wake-ups. Old Phase 5 runs retain their explicit resume path.

For installed local demo handlers, PostgreSQL effect/result/checkpoint/outbox atomicity permits recovery of an interrupted RUNNING call with its original key: either its transaction rolled back, or its completed result/cursor was saved. This exception is worker-only under the PostgreSQL execution fence and requires the installed LOCAL_DEMO_V1 metadata and idempotency support. It does not authorize automatic repetition of unknown external effects. Explicit retry of a failed run with an already successful/unknown side effect is blocked.
