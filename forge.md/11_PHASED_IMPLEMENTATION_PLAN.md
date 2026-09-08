# FORGE Phased Implementation Plan

Build one complete vertical slice at a time.

## Phase 0 — Architecture

Deliver this spec pack and architecture decisions.

## Phase 1 — Foundation

```text
FastAPI
config
Postgres
Alembic
health
errors
CI
Docker
```

Done when app boots, migration works, tests/CI pass.

## Phase 2 — Agent Registry

```text
organizations
agents
agent_versions
immutable versions
lifecycle
```

Done when v1/v2 can be created and history cannot be mutated.

## Phase 3 — Initial Runtime

```text
runs
run events
state machine
Gemini provider adapter
FORGE-owned runtime and state machine
single in-process execution (no queue)
```

Done when a run persists exact version + result.

## Phase 4 — Tool Hub

```text
FORGE tool registry
Tool Hub validation and policy boundary
schema validation
tool calls
lookup_customer
lookup_transactions
create_ticket
```

Phase 4 implementation and review are recorded in `../docs/PHASE_4_IMPLEMENTATION_REPORT.md`. Its small Tools UI extends the earlier local console; it does not complete the full dashboard roadmap. Review this slice before starting Phase 5.

## Phase 5 — Policy + Approval

Add FORGE PostgreSQL checkpoints and approval pause/resume, with restart-safe approval records and continuation state. Add `issue_refund` and deterministic policy:

```text
$50  → allow
$425 → approval
$700 → deny
```

## Phase 6 — Durability

```text
queue
worker
Redis
locks
FORGE checkpoint recovery
transactional outbox
idempotency
retry
timeout
cancel
```

Done when killing worker and restarting resumes without duplicate irreversible actions.

## Phase 7 — Model Router

```text
OpenAI provider adapter
primary/fallback
provider health
circuit breaker
cost tracking
```

## Phase 8 — Observability

```text
OpenTelemetry
structured logs
run traces
metrics
cost
```

## Phase 9 — Staging + Evaluation

```text
staging lifecycle
playground
evaluation suites
trajectory/cost/latency evaluation
```

## Phase 10 — Regression + Release Gate

```text
baseline comparison
gate rules
PASS/FAIL
approval status
```

A failing version cannot become production.

## Phase 11 — Deployment

```text
deployments
production pointer
REST access to deployed version
```

## Phase 12 — Rollback

```text
deployment history
rollback endpoint
audit
```

Done when:

```text
production v2.2
→ rollback
→ production v2.1
```

New requests use v2.1 immediately; existing runs stay on their original version.

## Phase 13 — Dashboard

Pages:

```text
Agents
Versions
Playground
Runs
Approvals
Evaluations
Deployments
```

## Phase 14 — SDK

Python first, TypeScript later.

## Six-Week Mapping

```text
Week 1: phases 1-3
Week 2: phases 4-5
Week 3: phase 6
Week 4: phases 7-8
Week 5: phases 9-10
Week 6: phases 11-14 + deployment polish
```

## Final Portfolio Demo

1. Create a versioned support agent.
2. Test in staging.
3. Run evaluation.
4. Demonstrate a failed release gate.
5. Create fixed version.
6. Pass gate.
7. Deploy production.
8. Run production request.
9. Pause on $425 refund approval.
10. Resume after approval.
11. Simulate Gemini failure and show fallback.
12. Show trace + cost.
13. Promote a deliberately degraded candidate in staging only.
14. Demonstrate incident reasoning.
15. Roll back production to previous stable version.

That tells a complete production engineering story.

## Runtime Implementation and Review Checkpoints

Phase 3 introduces a small FORGE-owned in-process execution path with a fake model for deterministic tests and a Gemini adapter. No durable recovery claim is made yet. Phase 4 routes every tool through the Tool Hub. Phase 5 adds persistent approval continuation and tests restart/resume. Phase 6 adds queue/workers, Redis locks, transactional outbox, durable checkpoint recovery, duplicate delivery, and crash tests. Phase 7 adds OpenAI, provider health, and coordinated fallback/retry accounting.

Finish each requested phase/session with the review map required by `10_CODEX_WORKING_RULES.md`. The six-week mapping is an estimate; user code review remains part of the work, and later phases do not start automatically.
