# FORGE Database Schema

PostgreSQL is the durable source of truth.

## Core Tables

```text
organizations
users
agents
agent_versions
deployments
deployment_history
runs
run_events
tools
agent_tools
tool_calls
policies
policy_rules
approvals
model_calls
evaluation_suites
evaluation_cases
evaluation_runs
evaluation_results
release_gates
release_decisions
audit_events
outbox_events
```

## agents

```text
id UUID PK
organization_id UUID FK
name TEXT
slug TEXT
description TEXT
status TEXT
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
UNIQUE(organization_id, slug)
```

## agent_versions

```text
id UUID PK
agent_id UUID FK
version TEXT
instructions TEXT
primary_model TEXT
fallback_models JSONB
runtime_config JSONB
budget_config JSONB
evaluation_suite_version_id UUID NULL
lifecycle_status TEXT
created_at TIMESTAMPTZ
UNIQUE(agent_id, version)
```

Runnable configuration and dependency bindings are immutable after creation.
Only lifecycle metadata may change through validated service transitions.

## deployments

```text
id UUID PK
organization_id UUID FK
agent_id UUID FK
environment TEXT
agent_version_id UUID FK
status TEXT
activated_at TIMESTAMPTZ
created_by UUID NULL
created_at TIMESTAMPTZ
UNIQUE(agent_id, environment)
```

## deployment_history

```text
id UUID PK
deployment_id UUID FK
from_version_id UUID NULL
to_version_id UUID FK
action TEXT
reason TEXT NULL
performed_by UUID NULL
created_at TIMESTAMPTZ
```

## runs

```text
id UUID PK
organization_id UUID FK
deployment_id UUID NULL
agent_id UUID FK
agent_version_id UUID FK
status TEXT
state_version INTEGER
input JSONB
output JSONB NULL
current_step INTEGER
model_calls_count INTEGER
tool_calls_count INTEGER
total_cost NUMERIC
started_at TIMESTAMPTZ NULL
completed_at TIMESTAMPTZ NULL
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

## run_events

```text
id UUID PK
run_id UUID FK
sequence_number INTEGER
event_type TEXT
payload JSONB
created_at TIMESTAMPTZ
UNIQUE(run_id, sequence_number)
```

## LangGraph checkpoint storage

Use the tables managed by the pinned `langgraph-checkpoint-postgres` package instead of a FORGE `run_checkpoints` table. Do not copy graph state into a competing recovery store. Checkpointer setup/upgrades run explicitly during deployment, separately from FORGE Alembic migrations and API startup.

The runtime phase adds a unique server-generated `graph_thread_id` to each run, plus runtime build/template revision metadata and any checkpoint reference needed for reconciliation. Domain state and graph state have separate transaction boundaries; see `13_LANGCHAIN_LANGGRAPH_RUNTIME.md`. Framework checkpoint access must go through organization-authorized FORGE services.

## tools

```text
id UUID PK
organization_id UUID FK NULL
name TEXT
version TEXT
description TEXT
input_schema JSONB
output_schema JSONB
risk_level TEXT
timeout_seconds INTEGER
retry_safe BOOLEAN
idempotency_supported BOOLEAN
handler_type TEXT
status TEXT
created_at TIMESTAMPTZ
```

## tool_calls

```text
id UUID PK
run_id UUID FK
tool_id UUID FK
status TEXT
arguments JSONB
result JSONB NULL
error JSONB NULL
idempotency_key TEXT UNIQUE
request_hash TEXT
started_at TIMESTAMPTZ NULL
completed_at TIMESTAMPTZ NULL
created_at TIMESTAMPTZ
```

## approvals

```text
id UUID PK
run_id UUID FK
tool_call_id UUID FK
status TEXT
summary TEXT
requested_payload JSONB
request_hash TEXT
expires_at TIMESTAMPTZ
requested_at TIMESTAMPTZ
reviewed_by UUID NULL
reviewed_at TIMESTAMPTZ NULL
decision_reason TEXT NULL
```

## model_calls

```text
id UUID PK
run_id UUID FK
provider TEXT
model TEXT
status TEXT
input_tokens INTEGER
output_tokens INTEGER
latency_ms INTEGER
estimated_cost NUMERIC
fallback_from TEXT NULL
error_type TEXT NULL
created_at TIMESTAMPTZ
```

## evaluation tables

Use versioned suites/cases and persist exact evaluator version/model metadata in result details.

## release_decisions

Store:

```text
agent_version_id
gate_id
evaluation_run_id
decision
metrics JSONB
reasons JSONB
created_at
```

## Important Indexes

```text
agents(organization_id, slug)
agent_versions(agent_id, version)
runs(agent_id, created_at DESC)
runs(status, created_at)
run_events(run_id, sequence_number)
tool_calls(run_id, created_at)
approvals(status, expires_at)
model_calls(run_id, created_at)
evaluation_runs(agent_version_id, created_at DESC)
deployment_history(deployment_id, created_at DESC)
```

## Binding Requirements for Later Migrations

`agent_tools` binds an immutable agent version to immutable tool revisions. Policies and evaluation suites/cases require immutable revisions and exact version bindings. Model configuration, provider model identifiers, and available provider revision metadata must be retained. Detailed columns/constraints will be implemented in their owning phases, following `12_ARCHITECTURE_DECISIONS.md`.

## Phase 2 Implemented Schema Additions

`organizations`: UUID id, name, globally unique slug, created_at. `agents`: organization FK, organization/slug uniqueness, ACTIVE/INACTIVE constraint, timestamps. `agent_versions`: agent FK, agent/version uniqueness, lifecycle constraint, plus `goal`, `runtime_template_revision`, immutable JSONB `tool_version_ids` and `policy_version_ids` alongside the configuration above. Reference arrays and the evaluation-suite UUID are draft intent until their registries exist; they do not yet have foreign keys to future tables. Later normalized bindings must agree with these immutable IDs.

Revision `0002_agent_registry` adds these tables and a PostgreSQL trigger function guarding version inserts (DRAFT only), updates (lifecycle metadata only, valid edge), deletes, and truncation. ORM metadata is registered in Alembic's environment. Migration downgrade drops version/agent/organization tables and the guard function; run downgrade only on disposable data or as an explicitly planned destructive operation.
