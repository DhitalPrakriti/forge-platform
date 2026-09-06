# Session Code Review Guide

Use this as the directory map for learning the project. Review the implementation after each session before moving to another phase. Session reports list the specific changed files; this guide explains how the existing pieces fit together.

## Current project: Phases 1–2

| Directory/files | Responsibility | Suggested review question |
| --- | --- | --- |
| `forge.md/` | Source-of-truth product, architecture, contracts, phase plan, working rules | What requirement authorizes this change? |
| `src/forge/main.py` | Creates FastAPI, owns resource lifespan, request trace IDs and unexpected-error boundary | When are resources created and closed? |
| `src/forge/core/config.py` | Loads and validates settings | What is required, and how are credentials represented? |
| `src/forge/core/errors.py` | Maps domain/HTTP/validation errors into the API contract | Can errors expose sensitive inputs? |
| `src/forge/db/base.py` | ORM base and naming conventions for future tables | What schema conventions will migrations use? |
| `src/forge/db/session.py` | Async engine, session factory, session dependency | Who commits, rolls back, and closes connections? |
| `src/forge/api/health.py` | Thin liveness/readiness routes | Is database work delegated to a service? |
| `src/forge/health/service.py` | Bounded database connectivity check | What happens on failure or timeout? |
| `src/forge/**/__init__.py` | Python package markers | These currently contain no behavior. |
| `migrations/env.py`, `alembic.ini` | Migration execution and configuration | Why is migration separate from API startup? |
| `migrations/versions/0001_foundation.py` | Empty migration baseline | Why do domain tables wait for Phase 2? |
| `migrations/script.py.mako` | Template for later migration files | What does a new revision need? |
| `tests/test_foundation.py` | Settings, health, timeout, errors, cleanup tests | Which behavior would a regression break? |
| `tests/test_postgres.py` | Real PostgreSQL migration and readiness test | Is the database disposable before downgrade? |
| `pyproject.toml`, `uv.lock`, `.python-version` | Package/dependencies, resolved versions, Python selection | Which dependencies are direct and why? |
| `Dockerfile`, `docker-compose.yml` | Container build and local service startup | Does migration finish before the API starts? |
| `.github/workflows/ci.yml` | Automated checks | Which checks ran locally versus only being configured? |
| `.env.example`, `.gitignore`, `.dockerignore` | Example settings and exclusions | Are local credentials/artifacts excluded? |
| `README.md` | Setup and verification commands | Can someone else run the current phase? |
| `docs/` | Review guides and session implementation records | What changed this session and what remains? |

`.venv/`, `.tools/`, caches, and `dist/` are generated local artifacts, not application source. Review their purpose and dependency lock rather than reading their generated contents line by line.

## First reading order

1. Read `forge.md/00_INDEX.md`, `02_SYSTEM_ARCHITECTURE.md`, and `10_CODEX_WORKING_RULES.md`.
2. Read `README.md`, `pyproject.toml`, and `.env.example`.
3. Follow `src/forge/main.py` into `core/config.py` and `db/session.py`.
4. Follow the health router into `health/service.py`, then read `core/errors.py`.
5. Read `db/base.py` and the migration files.
6. Read both test files and compare assertions with the API contract.
7. Read Docker/Compose/CI, then the session report's results and limitations.
8. Read `forge.md/13_LANGCHAIN_LANGGRAPH_RUNTIME.md` to understand the planned agent execution before Phase 3.

## Walkthrough: database readiness

```text
Uvicorn calls create_app()
  → Settings loads configuration
  → lifespan creates Database and its async pool
GET /api/v1/health/ready
  → middleware creates trace ID
  → health router calls check_database()
  → bounded SELECT 1 succeeds: 200 {status: ready}
  → database failure: DomainError → structured 503 + matching trace ID
Shutdown → lifespan disposes database engine
```

`main.py` currently starts the HTTP application; it does not run an agent. LangChain/LangGraph integration will be introduced in `runtime/` from Phase 3. That directory does not exist yet. Agent definitions now live in `agents/` (Phase 2).

## Required session handoff

For each session, supply:

1. Scope completed and behavior changed, in plain language.
2. Every added/modified/deleted file, grouped by directory, with purpose and relationships.
3. Dependency/configuration/migration changes and why they are needed.
4. Recommended reading order and a concrete request or failure walkthrough.
5. Commands executed, tests/results, and checks that could not run.
6. Review questions, unresolved issues, and the next phase without beginning it automatically.

Keep historical reports as records of what was true then. New decisions belong in new session notes and current specs, rather than silently rewriting old verification results.


## Phase 2 review path

Read `forge.md/03_AGENT_DEFINITION_AND_REGISTRY.md` and the Phase 2 section of `08_API_CONTRACT.md`, then:

| Order / file | Responsibility and relationship |
| --- | --- |
| 1. `src/forge/agents/schemas.py` | Request/response shapes; validates names, references, limits and editable fields. |
| 2. `src/forge/agents/lifecycle.py` | State names and allowed transitions; used by the service. |
| 3. `src/forge/agents/models.py` | Organization, agent, immutable-version ORM tables. |
| 4. `src/forge/agents/repository.py` | Organization-scoped SQL queries and row locks; called by the service. |
| 5. `src/forge/agents/service.py` | Business validation and commits; calls repository and lifecycle rules. |
| 6. `src/forge/api/registry.py` | Development scope dependency, production block, thin routes calling services. |
| 7. `src/forge/main.py` | Registers the registry router alongside health. |
| 8. `migrations/versions/0002_agent_registry.py` | Tables and PostgreSQL immutability/lifecycle triggers. |
| 9. `migrations/env.py` | Imports registry model metadata for migration comparison. |
| 10. `tests/test_registry_validation.py`, `tests/test_registry_postgres.py` | Invalid input, scope isolation, history, concurrency and database guard checks. |
| 11. `tests/test_postgres.py` | Migration round trip now expects Phase 2 head. |

`src/forge/agents/__init__.py` is a package marker; no hidden behavior. No LangChain/LangGraph imports have been added yet.

### Walkthrough: create version v2

```text
POST /api/v1/agents/{agent_id}/versions + X-Organization-ID
  → reject production access until authenticated membership exists
  → VersionCreate validates configuration (client cannot set lifecycle)
  → RegistryService resolves organization-scoped agent with row lock
  → reject inactive agent
  → Repository adds AgentVersion containing the complete configuration snapshot
  → PostgreSQL checks agent/version uniqueness and DRAFT-only insertion
  → Service commits; API returns 201 with exact snapshot and UUID
```

A concurrent duplicate creates no second version and gets 409. Updating the agent's name later does not alter the version. Direct SQL edits of version configuration, DELETE, and TRUNCATE are rejected by database triggers. These guards are not protection from a database administrator deliberately disabling them.

Questions for your review: Which fields can change? Where is organization scoping applied? Why is the organization header not authentication? Why is staging blocked? How do row locks and unique constraints differ? Which rules are enforced by both service and database?
