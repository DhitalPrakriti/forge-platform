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

## Phase 3 Development Runtime API

These endpoints use the same local/test organization selector as registry requests and are disabled in production until authenticated membership exists.

```text
POST /runs
GET  /runs/{run_id}
GET  /runs/{run_id}/events
GET  /runs/{run_id}/model-calls
```

POST requires UUID `X-Organization-ID` and `Idempotency-Key` (1–200 ASCII letters/digits or `.`, `_`, `:`, `-`). Example body (replace UUID with an actual version ID):

```json
{
  "agent_version_id": "00000000-0000-0000-0000-000000000001",
  "input": {"message": "Explain what you can help with."}
}
```

The POST waits for the initial execution and returns 201 for a new saved run, even if its model execution failed; inspect `status`, `error_code`, and `output`. A repeated key with identical normalized input returns 200 and the existing run, possibly still RUNNING. A conflicting payload returns 409 `IDEMPOTENCY_CONFLICT`. Run GET returns the same stored representation. Events accept `after` (exclusive sequence, default -1) and `limit` (1–100, default 50). Model-call GET returns execution evidence; no raw provider exception strings or credentials. Cross-organization run IDs return 404 `RUN_NOT_FOUND`.

Phase 3 accepts standard-agent-v1 DRAFT/STAGING versions from active agents, with no tools, policy bindings, or fallback models. Unsupported configuration returns 409 `RUNTIME_CONFIGURATION_UNSUPPORTED`; inactive/other lifecycle returns 409 `VERSION_NOT_RUNNABLE`. Missing key returns 503 `MODEL_NOT_CONFIGURED` before run creation; unsupported non-Gemini model in Gemini mode returns 422 `MODEL_UNSUPPORTED`. Input messages must contain 1–20000 characters after trimming.

Persisted execution failure codes include MODEL_TIMEOUT, MODEL_AUTH_FAILED, MODEL_PROVIDER_UNAVAILABLE, MODEL_REQUEST_REJECTED, MODEL_INTERNAL_ERROR, MODEL_RESPONSE_INCOMPLETE and TOOL_CALLING_NOT_IMPLEMENTED. A 201 means the run resource was created, not that the model succeeded. Real cost remains null; budget enforcement is explicitly NOT_IMPLEMENTED_PHASE_3. Calls may incur provider charges in Gemini mode. No production deployment, retry, replay, cancellation, or tool execution endpoint is added here.

## Phase 4 Tool Hub contract

These development-only endpoints use the same UUID organization scope and production authentication block as the registry. No arbitrary tool-code execution route is exposed.

| Route | Contract |
| --- | --- |
| `POST /tools` | `{ "name": "lookup_customer", "version": "1.0.0" }`; installed names are lookup_customer, lookup_transactions, create_ticket. Version defaults to 1.0.0. Returns 201 on registration or 200 for the existing exact revision; concurrent registration is deduplicated. Metadata is server-owned. |
| `GET /tools` | Organization's revisions, limit 1–100 and nonnegative offset; creation-time/ID order. |
| `GET /tools/{tool_id}` | Exact organization-owned metadata and schemas; foreign/missing IDs return 404 TOOL_NOT_FOUND. |
| `PATCH /tools/{tool_id}` | Only `{ "status": "ACTIVE" }` or INACTIVE; schema/handler/name/version edits return 422. Existing versions retain their IDs, but inactive tools cannot newly execute. |
| `GET /runs/{run_id}/tool-calls` | Paginated recorded attempts, limit 1–100/offset; ownership checked on the run. Includes exact tool ID (nullable for unbound/unknown), requested name, model-call ID, index, arguments, result/error, status/decision, hash/key, latency/timestamps. |

The run request body/idempotency contract is unchanged. New versions now validate tool IDs against this registry and persist normalized permissions. Unknown/foreign IDs return 404 TOOL_NOT_FOUND, inactive tools 409 TOOL_INACTIVE, missing/changed installed metadata 409 TOOL_REVISION_UNAVAILABLE, duplicate names 409 TOOL_NAME_AMBIGUOUS. Existing legacy unresolved drafts are not silently upgraded.

Phase 4 runs support exact registered tool revisions. Policy/fallback bindings remain unsupported. New persisted errors include TOOL_NOT_ALLOWED, TOOL_VALIDATION_FAILED, POLICY_DENIED, TOOL_OUTPUT_INVALID, TOOL_INTERNAL_ERROR, TOOL_TIMEOUT, RUN_TIMEOUT, STEP_LIMIT_EXCEEDED, TOOL_CALL_LIMIT_EXCEEDED, DEMO_CUSTOMER_NOT_FOUND, TOOL_OUTCOME_UNKNOWN, and FAKE_TOOL_REQUEST_INVALID. Phase 3's TOOL_CALLING_NOT_IMPLEMENTED applies to historical runs; current unpermitted tool requests are recorded and denied.

Example fake test message after binding lookup_customer: `/tool lookup_customer {"customer_id":"cust_001"}`. A successful tool flow records two model calls and one tool call. The command does not switch the server's configured provider. Current monetary enforcement is DEFERRED_TO_PHASE_7; policy boundary is LOCAL_DEMO_ONLY_PHASE_4. Refund approvals and external side effects remain unavailable.
