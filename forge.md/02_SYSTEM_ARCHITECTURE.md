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
                     LangGraph Engine
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
→ runtime loads pinned config into LangChain create_agent / LangGraph
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
LangGraph
LangChain (create_agent, messages, tools, middleware)
LangChain Gemini integration
LangChain OpenAI integration
LangGraph PostgreSQL checkpointer
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

## Framework Ownership

Use LangChain `create_agent` (built on LangGraph) for the standard model/tool loop. FORGE services supply versioned configuration and deterministic tool middleware/wrappers. LangGraph owns graph scheduling, checkpoint state, and interrupt/resume. `runtime/` contains the integration; do not add a separate workflow engine. Use an explicit `StateGraph` only when a documented requirement cannot be expressed clearly with standard agents/middleware.

FORGE owns database run status, tool/approval records, authorization, limits, queue delivery, evaluation, and deployment decisions. LangGraph checkpoints use its PostgreSQL checkpointer; FORGE domain tables remain SQLAlchemy/Alembic-owned. See `13_LANGCHAIN_LANGGRAPH_RUNTIME.md` for consistency boundaries and staged adoption. Open-source packages run inside our API/worker; a hosted LangSmith service is not required.
