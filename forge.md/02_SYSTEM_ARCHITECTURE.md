# FORGE System Architecture

## High-Level Architecture

```text
                    Agent Builder / API
                            │
                            ▼
                     Agent Registry
                            │
                     Immutable Versions
                            │
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
          Runtime        Tool Hub      Model Router
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                     Workflow Engine
                            │
                ┌───────────┼───────────┐
                ▼           ▼           ▼
             Postgres      Redis       Queue
                │                        │
                │                        ▼
                │                     Workers
                └────────────┬───────────┘
                             ▼
                          Run State
                             │
                             ▼
                       Observability
                  ┌──────────┼──────────┐
                  ▼          ▼          ▼
                Logs       Traces    Metrics/Cost
                             │
                             ▼
                         Evaluation
                             │
                             ▼
                   Regression Comparison
                             │
                             ▼
                       Release Gate
                             │
                         PASS/BLOCK
                             │
                             ▼
                         Deployment
                             │
                 ┌───────────┼───────────┐
                 ▼           ▼           ▼
             Playground      API     Future Channels
                             │
                             ▼
                       Production Runs
                             │
                             ▼
                          Rollback
```

## Control Plane vs Execution Plane

### Control Plane

Stores what **should** happen:

```text
agents
versions
policies
evaluation suites
release gates
deployments
```

### Execution Plane

Performs what **is happening now**:

```text
runs
workers
model calls
tool calls
approvals
checkpoints
```

## Core Request Path

```text
Client request
→ authenticate/validate
→ resolve deployment
→ resolve immutable agent version
→ create run in Postgres
→ enqueue
→ worker locks run
→ FORGE runtime loads pinned configuration
→ model router calls provider
→ LLM returns text/tool request
→ Tool Hub validates
→ Policy evaluates
→ ALLOW / DENY / APPROVAL
→ checkpoint
→ continue until terminal
→ persist output + telemetry
```

## Modular Monolith

Initial deployables:

```text
API service
Worker service
PostgreSQL
Redis
Queue
```

Internal modules:

```text
agents/
runtime/
tools/
policies/
approvals/
model_router/
deployments/
evals/
releases/
observability/
```

## Technology Baseline

```text
Python 3.12+
FastAPI
Pydantic
SQLAlchemy 2.x
Alembic
PostgreSQL
Redis
Cloud Tasks or Dramatiq
Gemini provider SDK behind adapter
OpenAI provider SDK behind adapter
OpenTelemetry
pytest
Docker
GitHub Actions
GCP Cloud Run
Cloud SQL
Secret Manager
```

## Phase 1 Foundation Decisions

Use a `src/forge` package, an application factory with lifespan-managed database resources, PostgreSQL 16 for local/CI development, and asyncpg behind SQLAlchemy async sessions. Alembic owns schema changes and runs separately from API startup. Dependency resolution is committed in `uv.lock`. Phase 1 deploys only API and PostgreSQL; worker/Redis/queue arrive in Phase 6. See `12_ARCHITECTURE_DECISIONS.md`.

## Runtime Ownership

FORGE owns the execution loop, state transitions, checkpointing, and approval pause/resume. Keep the initial implementation small in `runtime/`; workflow behavior belongs there until a concrete need justifies another module. Provider SDKs stay behind adapters. PostgreSQL stores platform and execution state through SQLAlchemy/Alembic; Redis supports coordination when introduced in Phase 6.

LangChain/LangGraph are optional future adapter candidates, not V1 dependencies. No graph database is required. See `14_FORGE_RUNTIME_DECISION.md`.
