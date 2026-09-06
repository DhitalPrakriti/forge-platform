# Observability, Reliability, and Security

## Observability Goal

For any failed production run, answer:

```text
which agent/version?
which model/provider?
which tool?
which policy?
which approval?
where did it fail?
how many retries?
how long?
how much did it cost?
```

## Structured Logs

Include:

```text
timestamp
level
trace_id
organization_id
agent_id
agent_version_id
run_id
event_type
```

Never log secrets or full sensitive payloads.

## Traces

OpenTelemetry parent span:

```text
forge.run
```

Children:

```text
forge.model_call
forge.tool_call
forge.policy_evaluation
forge.approval_wait
forge.checkpoint
```

## Metrics

Counters:

```text
forge_runs_total
forge_run_failures_total
forge_model_calls_total
forge_tool_calls_total
forge_policy_denials_total
forge_rollbacks_total
```

Histograms:

```text
forge_run_latency_seconds
forge_model_latency_seconds
forge_tool_latency_seconds
forge_run_cost_usd
```

Gauges:

```text
forge_active_runs
forge_queue_depth
forge_pending_approvals
```

## Reliability Patterns

Required:

```text
timeouts
retry classification
exponential backoff + jitter
circuit breaker
idempotency
distributed locking
optimistic concurrency
durable checkpoints
failure visibility
```

## Security Rules

1. Provider secrets stay server-side.
2. LLM never receives raw credentials.
3. Tool inputs use schema validation.
4. Policy executes before high-impact actions.
5. Approval binds to exact request hash.
6. Organization isolation enforced.
7. Secrets stored in Secret Manager.
8. No business logic in frontend.
9. Sensitive trace/log redaction.
10. Release/deployment/rollback actions audited.

## Prompt Injection

Prompt injection cannot bypass deterministic Tool Hub/Policy controls.

## Failure Injection

Dev-only controls can simulate:

```text
model timeout
tool failure
provider 500
```

Useful for demonstrating retries, fallback, and resilience.
