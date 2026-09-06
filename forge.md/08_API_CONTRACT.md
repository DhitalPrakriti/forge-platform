# FORGE API Contract

Base:

```text
/api/v1
```

## Agents

```text
POST   /agents
GET    /agents
GET    /agents/{agent_id}
PATCH  /agents/{agent_id}
POST   /agents/{agent_id}/versions
GET    /agents/{agent_id}/versions
GET    /agents/{agent_id}/versions/{version_id}
```

Historical versions cannot be edited.

## Lifecycle

```text
POST /agent-versions/{version_id}/stage
POST /agent-versions/{version_id}/evaluate
POST /agent-versions/{version_id}/release-check
POST /agent-versions/{version_id}/archive
```

## Playground

```text
POST /playground/runs
```

Example:

```json
{
  "agent_version_id": "ver_123",
  "input": {"message": "Research Shopify"},
  "execution_mode": "DRY_RUN"
}
```

## Production Runs

Friendly alias:

```text
POST /agents/{agent_slug}/runs
```

Server resolves current production deployment.

Explicit:

```text
POST /deployments/{deployment_id}/runs
```

## Runs

```text
GET  /runs/{run_id}
GET  /runs/{run_id}/events
POST /runs/{run_id}/cancel
POST /runs/{run_id}/retry
POST /runs/{run_id}/replay
```

## Tools

```text
POST  /tools
GET   /tools
GET   /tools/{tool_id}
PATCH /tools/{tool_id}
```

## Approvals

```text
GET  /approvals
GET  /approvals/{approval_id}
POST /approvals/{approval_id}/approve
POST /approvals/{approval_id}/deny
```

## Evaluation

```text
POST /evaluation-suites
POST /evaluation-suites/{suite_id}/cases
POST /evaluation-runs
GET  /evaluation-runs/{evaluation_run_id}
GET  /evaluation-runs/{evaluation_run_id}/results
```

## Deployments

```text
POST /deployments
GET  /deployments
GET  /deployments/{deployment_id}
POST /deployments/{deployment_id}/promote
POST /deployments/{deployment_id}/rollback
POST /deployments/{deployment_id}/disable
```

## Error Contract

```json
{
  "error": {
    "code": "RELEASE_GATE_FAILED",
    "message": "This version has not passed the production release gate.",
    "trace_id": "tr_123",
    "details": {}
  }
}
```

Useful codes:

```text
AGENT_NOT_FOUND
VERSION_NOT_FOUND
VERSION_IMMUTABLE
INVALID_LIFECYCLE_TRANSITION
RUN_NOT_FOUND
INVALID_RUN_STATE
TOOL_VALIDATION_FAILED
POLICY_DENIED
APPROVAL_EXPIRED
MODEL_TIMEOUT
MODEL_PROVIDER_UNAVAILABLE
BUDGET_EXCEEDED
RELEASE_GATE_FAILED
DEPLOYMENT_NOT_FOUND
ROLLBACK_TARGET_NOT_FOUND
```

Critical POSTs should accept `Idempotency-Key`.

## Foundation Health Endpoints

- `GET /api/v1/health/live`: 200 when the HTTP process can respond; no database query.
- `GET /api/v1/health/ready`: 200 when PostgreSQL responds to a bounded query; 503 with `DATABASE_UNAVAILABLE` otherwise. This is connectivity readiness, not a migration-version check.
- Responses carry a server-generated `X-Trace-ID`; structured errors contain the same ID.

Retry and replay endpoints create new runs as specified in `12_ARCHITECTURE_DECISIONS.md`; they do not reopen terminal runs. Tool PATCH changes administrative metadata only; executable/schema changes require a new immutable revision.

## Phase 2 Registry Requests

Development-only organization bootstrap: `POST /organizations` with `{ "name": "Demo", "slug": "demo" }`; returns 201. `GET /organizations/current` returns the selected organization. All other registry routes require a UUID `X-Organization-ID` header in local/test mode. Production registry routes return structured 503 `REGISTRY_AUTH_REQUIRED` until real membership authentication exists.

`POST /agents` takes name, lowercase hyphenated slug, optional description; returns 201. PATCH accepts only non-null name, description, or ACTIVE/INACTIVE status. Agent and version list routes return arrays with `limit` (1–100, default 50) and `offset` (nonnegative, default 0), ordered by creation time then ID.

Example version creation body:

```json
{
  "version": "v1",
  "goal": "Help customers",
  "instructions": "Answer clearly and follow policy.",
  "primary_model": "gemini-2.5-flash",
  "fallback_models": [],
  "runtime_template_revision": "standard-agent-v1",
  "runtime_config": {"max_steps": 12, "max_runtime_seconds": 180},
  "budget_config": {"max_cost_per_run_usd": "0.20"},
  "tool_version_ids": [],
  "policy_version_ids": [],
  "evaluation_suite_version_id": null
}
```

Lifecycle status is server-owned. Unknown fields and malformed limits return structured 422. Currency uses Decimal and JSON string serialization. Creation returns 201; duplicate organization slug, agent slug in an organization, or version label in an agent returns 409 with `ORGANIZATION_SLUG_EXISTS`, `AGENT_SLUG_EXISTS`, or `VERSION_EXISTS`. Uniqueness prevents duplicate records on retry; registry creation does not yet replay responses using an `Idempotency-Key` store. Critical execution/approval/deployment idempotency belongs to their owning phases.

Version PATCH returns 409 `VERSION_IMMUTABLE` after organization/parent validation. Archive changes lifecycle metadata only and returns the version; repeated/invalid archive returns 409 `INVALID_LIFECYCLE_TRANSITION`. Staging returns 409 `EVALUATION_SUITE_REQUIRED` or `STAGING_DEPENDENCIES_UNAVAILABLE` until later validation registries exist. No evaluation/release/promotion endpoint is implemented in Phase 2.
