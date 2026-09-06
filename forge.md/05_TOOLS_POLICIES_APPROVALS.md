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

## LangChain / LangGraph Integration

Register tools through LangChain's tool interface, with FORGE middleware/wrappers enforcing the entire pipeline above for every invocation. A built-in agent loop or tool executor must never provide an alternate unguarded execution route. V1 processes side-effecting tools serially to simplify approval and idempotency review.

Persist an idempotent approval request before LangGraph `interrupt()`. The FORGE endpoint authenticates the reviewer and commits the exact decision; only the service may translate it into `Command(resume=...)`. A raw client resume value is not authorization. Re-read the approved record and revalidate binding/expiry before execution. See `13_LANGCHAIN_LANGGRAPH_RUNTIME.md`.
