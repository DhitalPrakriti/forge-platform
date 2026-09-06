# Staging, Evaluation, Release, Deployment, and Rollback

This lifecycle is a core differentiator of FORGE.

## Full Lifecycle

```text
CREATE VERSION
↓
STAGING
↓
PLAYGROUND / DRY-RUN
↓
AUTOMATED EVALUATION
↓
REGRESSION VS CURRENT PRODUCTION
↓
RELEASE GATE
↓
PASS? ──NO──→ BLOCKED → CREATE FIXED VERSION
  │
 YES
  ↓
APPROVED
↓
DEPLOY
↓
PRODUCTION
↓
OBSERVE
↓
HEALTHY? ──NO──→ ROLLBACK
```

## Staging

Staging is runnable but not normal production traffic.

Supports:

- manual Playground tests;
- dry-run tools;
- mock tools;
- evaluation suites;
- failure injection.

Irreversible actions should default to DRY_RUN in staging/evaluation.

## Evaluation

Versioned suite measures:

```text
task success
tool correctness
tool arguments
policy compliance
hallucination/safety proxy
cost
latency
```

Evaluator types:

```text
deterministic
trajectory
LLM judge
cost
latency
human
```

## Regression Comparison

Example:

```text
Metric              v2.1 prod   v2.2 candidate
Task success        92%         95%
Tool correctness    97%         96%
Average cost        $0.031      $0.047
P95 latency         2.1s        1.9s
```

FORGE should identify both absolute threshold failures and unacceptable degradation versus baseline.

## Release Gate

Example deterministic rules:

```json
{
  "task_success_min": 0.92,
  "tool_correctness_min": 0.95,
  "average_cost_max": 0.05,
  "p95_latency_ms_max": 3000
}
```

Overall result:

```text
PASS
FAIL
```

An LLM does not decide promotion.

## Deployment

A deployment is a pointer:

```text
(environment, agent) → exact immutable agent_version_id
```

Example:

```text
production/company-research-agent → v2.2
```

Deployment access V1:

- Playground;
- REST API.

## Rollback

Rollback changes the production pointer back to a known-good version.

```text
before: production → v2.2
rollback: production → v2.1
```

Do not edit v2.2 in place.

Persist:

```text
from_version
to_version
reason
actor
timestamp
```

Existing runs stay attached to the version they started with. New runs resolve the newly active production version.

## Future

Later:

- shadow evaluation;
- canary release;
- automatic rollback.

Do not build these first.

## V1 Gate and Pointer Authority

`deployments.agent_version_id` is the sole active-version authority per agent/environment. Promotion atomically validates the gate evidence, changes the pointer, and appends deployment history/audit records. V1 has no release-gate override. Rollback targets a previously deployed known-good immutable version of the same agent/environment and records the change atomically. See `12_ARCHITECTURE_DECISIONS.md`.
