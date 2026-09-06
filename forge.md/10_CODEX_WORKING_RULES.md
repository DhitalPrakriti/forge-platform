# Codex Working Rules for FORGE

Codex is an implementation partner, not the architecture authority. These Markdown specifications are the source of truth.

## Global Rules

1. Read the relevant spec before editing code.
2. Implement only the requested phase.
3. Do not add unrelated future features.
4. Maintain modular-monolith boundaries.
5. Keep FastAPI handlers thin.
6. Put business logic in service/domain modules.
7. Use SQLAlchemy 2.x and Alembic.
8. Add tests with every feature.
9. Run tests before completion.
10. Keep LangChain provider integrations behind thin adapters; prefer ecosystem interfaces over direct provider SDK plumbing.
11. Never use LLM output for authorization.
12. Preserve version immutability.
13. Do not introduce microservices/Kubernetes/Kafka without explicit later instruction.
14. Explain new dependencies before adding them.
15. Do not expose secrets.

## Required Completion Report

After each task, report:

```text
1. implemented functionality
2. files changed
3. migration added
4. tests added
5. commands run
6. test results
7. unresolved issues
8. recommended next step
```

## Foundation Prompt

```text
Read 00_INDEX.md, 02_SYSTEM_ARCHITECTURE.md, and 10_CODEX_WORKING_RULES.md.

Implement only project foundation:
- FastAPI
- Pydantic Settings
- SQLAlchemy 2.x async
- Alembic
- PostgreSQL
- health endpoints
- structured errors
- pytest
- ruff
- Dockerfile
- docker-compose
- GitHub Actions CI

Do not implement agents yet.
```

## Agent Registry Prompt

```text
Read 03_AGENT_DEFINITION_AND_REGISTRY.md, 07_DATABASE_SCHEMA.md, 08_API_CONTRACT.md.

Implement organizations, agents, agent_versions, lifecycle validation, immutable versions, migrations, repository/service layers, APIs, and tests.

Do not implement runtime yet.
```

## Runtime Prompt

```text
Read 04_RUNTIME_AND_STATE_MACHINE.md and 13_LANGCHAIN_LANGGRAPH_RUNTIME.md.

Implement runs, run_events, state enum, transition validation, initial in-process LangChain create_agent execution on LangGraph, thin LangChain Gemini adapter, model_call persistence, and tests.

Do not add Redis/queue yet.
```

## Tool/Policy Prompt

```text
Read 05_TOOLS_POLICIES_APPROVALS.md.

Implement LangChain tools with FORGE validation/policy middleware, demo tools, deterministic refund policy, approvals, LangGraph PostgreSQL checkpointing and interrupt/resume, and tests.
```

## Durability Prompt

```text
Read 04_RUNTIME_AND_STATE_MACHINE.md and 09_OBSERVABILITY_RELIABILITY_SECURITY.md.

Implement queue abstraction, worker, Redis run locks, LangGraph checkpoint/domain reconciliation, idempotency, retry/backoff, cancellation, timeout, duplicate-delivery tests, and worker-recovery tests.
```

## Evaluation/Release Prompt

```text
Read 06_STAGING_EVALUATION_RELEASE_DEPLOY_ROLLBACK.md.

Implement evaluation suites/cases/runs/results, deterministic and trajectory evaluators, cost/latency metrics, regression comparison, release gates, and tests.
```

## Deployment/Rollback Prompt

```text
Read 06_STAGING_EVALUATION_RELEASE_DEPLOY_ROLLBACK.md, 07_DATABASE_SCHEMA.md, 08_API_CONTRACT.md.

Implement deployments, deployment_history, gate enforcement, atomic production promotion, manual rollback, audit records, and tests.

Rollback must point to an immutable previous version.
```

## Framework and Session Review Rules

- Read `13_LANGCHAIN_LANGGRAPH_RUNTIME.md` before runtime/tool/model work.
- Prefer LangChain standard agent APIs and LangGraph persistence/interrupts. Do not hand-write a competing agent loop, scheduler, or checkpointer.
- Keep FORGE authorization, tool validation, release gates, and side-effect idempotency explicit and tested.
- Keep code changes within the requested phase and organize them into understandable responsibilities. Avoid speculative abstractions and empty future module directories.
- At session completion, list every changed file and directory, explain its purpose and caller/callee relationships, and give a recommended reading order plus one concrete request walkthrough.
- State dependencies, migrations, commands, results, limitations, and review questions. Distinguish planned modules from existing code and generated artifacts.
- Maintain `docs/CODE_REVIEW_GUIDE.md` as structure evolves. Add a session record under `docs/` for substantive changes. Do not automatically begin the next phase after a session report.
