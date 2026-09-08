# Agent Definition and Registry

## Key Principle

FORGE V1 does not require developers to bring a fully running agent. They create an **Agent Definition** and FORGE owns the runtime and state machine.

## Agent Definition Contains

```text
name
goal
instructions
primary model
fallback models
tools
policies
runtime limits
budget limits
evaluation suite
```

## Agent vs Version vs Run

```text
Agent        = logical identity
Agent Version= immutable runnable configuration
Run          = one execution of one exact version
```

Example:

```text
support-agent
├── v1.0
├── v1.1
└── v2.0
    ├── run_001
    ├── run_002
    └── run_003
```

## Why Version Immutability Matters

Historical runs must always answer:

```text
Which prompt?
Which model?
Which tools?
Which policies?
Which limits?
```

Therefore a change creates a new version, never edits an old one.

## Lifecycle

```text
DRAFT
↓
STAGING
↓
EVALUATING
↓
APPROVED
↓
PRODUCTION
↓
DEPRECATED
↓
ARCHIVED
```

## Validation Before Staging

Reject staging when:

- primary model config invalid;
- referenced tool missing;
- policy missing;
- runtime limits malformed;
- required evaluation suite absent.

## Built-In vs Custom Tools

Built-in example:

```text
web_search
read_url
calculator
search_documents
```

Custom tool example:

```text
lookup_customer
issue_refund
create_jira_ticket
```

The developer supplies custom integration code/API, but FORGE still controls schema, policy, execution, tracing, and retries.

## Configuration and Lifecycle Boundary

Runnable configuration is immutable from creation, including tool, policy, model configuration, and evaluation-suite version bindings. Lifecycle status is mutable operational metadata changed only through validated transitions. Production deployment membership is determined by deployments, not lifecycle status alone. See `12_ARCHITECTURE_DECISIONS.md`.

Agent versions also pin a runtime template revision. Runs record the actual runtime build versions so checkpoint recovery uses compatible code. See `14_FORGE_RUNTIME_DECISION.md`.

## Phase 2 Registry Contract

Versions are created as DRAFT only. Required configuration: version label, goal, instructions, primary model. Runtime/budget defaults are validated and persisted; runtime template revision is pinned. Optional tool/policy/evaluation UUID references are immutable draft intent, not verified dependencies. Staging fails with `EVALUATION_SUITE_REQUIRED` if no suite is supplied and `STAGING_DEPENDENCIES_UNAVAILABLE` otherwise until the owning registries can validate all references. This prevents Phase 2 from asserting successful staging prematurely.

Allowed lifecycle edges are DRAFT → STAGING/ARCHIVED; STAGING → EVALUATING/ARCHIVED; EVALUATING → STAGING/APPROVED; APPROVED → PRODUCTION/ARCHIVED; PRODUCTION → DEPRECATED; DEPRECATED → PRODUCTION/ARCHIVED; ARCHIVED has no outgoing edge. Self-transitions are rejected by services. Later evaluation/deployment services must add their evidence checks before invoking these edges. Phase 2 exposes only archive and guarded staging, not evaluation, approval, promotion, or rollback.

Agent name/description/ACTIVE-INACTIVE status may change; slug and organization identity do not change through PATCH. Inactive agents remain readable but cannot receive new versions. No delete endpoint exists. Configuration updates and deletion/truncation of version history are rejected by PostgreSQL triggers as well as the API. These guards protect ordinary database writes, not an administrator deliberately disabling triggers or dropping tables.

Until authenticated membership is implemented, registry endpoints are development-only: local/test requests select an organization with `X-Organization-ID`; production registry requests return `REGISTRY_AUTH_REQUIRED`. This header is a development context selector, not an authorization credential. Every agent/version query is constrained to that selected organization, and cross-organization IDs return 404. Do not expose local/test mode to untrusted clients.
