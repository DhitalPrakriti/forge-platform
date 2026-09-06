# FORGE

FORGE is a production control plane for AI agents. The source of truth is [the specification pack](forge.md/00_INDEX.md). Phases 1–2 are implemented: foundation and the development agent registry.

## Included

FastAPI application factory, Pydantic Settings, SQLAlchemy 2.x async PostgreSQL connections/sessions, Alembic baseline, health endpoints, structured errors, tests, Ruff, locked dependencies, Docker Compose, and GitHub Actions CI.

## Local setup

Install Python 3.12+ and uv (the lockfile was generated with uv 0.12.10). A workspace-local uv bootstrap is available at `.tools/bin/uv` on the development machine; substitute that for `uv` if it is not on PATH.

```sh
uv sync --frozen --python 3.12
cp .env.example .env
```

Start PostgreSQL 16, creating the database/user specified in `.env`. With Docker installed:

```sh
docker compose up -d db
uv run alembic upgrade head
uv run uvicorn forge.main:create_app --factory --reload
```

Then open `/docs` at `http://localhost:8000`, or:

```sh
curl --fail http://localhost:8000/api/v1/health/live
curl --fail http://localhost:8000/api/v1/health/ready
```

Liveness returns 200 independently of PostgreSQL. Readiness returns 200 on database connectivity or a structured 503 on failure. It does not verify schema migration head. Apply migrations before serving traffic.

To run the complete local stack:

```sh
docker compose up --build --wait api
```

Compose waits for PostgreSQL health, runs a one-shot migration, then starts the API as a non-root container user. Credentials in Compose and `.env.example` are local examples. Supply production secrets externally; never commit `.env`. No production deployment has been configured or performed.

## Configuration

| Variable | Behavior |
| --- | --- |
| `FORGE_DATABASE_URL` | Required `postgresql+asyncpg://` URL naming a database; treated as secret in settings. |
| `FORGE_ENVIRONMENT` | `local` (default), `test`, or `production`. |
| `FORGE_DATABASE_TIMEOUT_SECONDS` | Database readiness/connect timeout, greater than 0 and at most 60; default 3 seconds. |

Environment variables override `.env`. API startup does not migrate the database. Services will own transaction commits; closing uncommitted sessions rolls back. Error bodies follow the spec and carry a server-generated trace ID, also sent in `X-Trace-ID`. Unexpected errors emit a sanitized code/trace ID log without traceback payloads; full observability belongs to Phase 8.

## Verification

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

The PostgreSQL integration test skips unless `FORGE_TEST_DATABASE_URL` is set. It upgrades and downgrades the schema: use a disposable database only.

```sh
FORGE_TEST_DATABASE_URL=postgresql+asyncpg://forge:forge_local@localhost:5432/forge_test uv run pytest -q
uv run alembic current
uv run alembic check
uv build
```

Create `forge_test` first. The ordinary `FORGE_DATABASE_URL` is used by standalone Alembic commands. CI supplies its own PostgreSQL test database, runs all tests and lint, verifies migrations, builds the container, and checks Compose readiness.

## Layout

- `src/forge/api`: thin HTTP routes.
- `src/forge/core`: configuration and structured errors.
- `src/forge/db`: declarative base and async resource/session management.
- `src/forge/health`: database health service.
- `migrations`: Alembic environment and empty Phase 1 baseline.
- `tests`: configuration, health, error, lifecycle cleanup, timeout, and PostgreSQL tests.
- `forge.md`: source-of-truth specs and architecture decisions.
- `docs/PHASE_1_IMPLEMENTATION_REPORT.md`: detailed change and verification record.

Organization, agent, and immutable version tables are implemented. Agent execution, worker/Redis/queue, model integrations, authentication, evaluations, and dashboards remain in later phases.

## Architecture direction and session reviews

Agent execution will use LangChain `create_agent` on LangGraph, with FORGE's deterministic controls around tools and production operations. See [runtime design](forge.md/13_LANGCHAIN_LANGGRAPH_RUNTIME.md). Framework packages arrive with their implementation phases; the current app implements Phase 2 registry operations.

Start each code review with [the directory and walkthrough guide](docs/CODE_REVIEW_GUIDE.md). Session reports explain each changed file, its purpose, validation results, and limitations.


## Phase 2: review the registry

Apply `uv run alembic upgrade head`, then use `/docs` to:

1. `POST /api/v1/organizations` with a name and slug; copy the returned UUID.
2. Supply that UUID as `X-Organization-ID` for registry requests.
3. `POST /api/v1/agents` with name, slug, and optional description.
4. Create v1 and v2 using `POST /api/v1/agents/{agent_id}/versions`; see the exact body in [the API contract](forge.md/08_API_CONTRACT.md).
5. List/read the versions, change agent metadata, and verify historical configuration is unchanged.
6. Archive a DRAFT version. Editing its configuration returns `VERSION_IMMUTABLE`.

The organization header is a development selector, **not authentication**. Registry routes are disabled when `FORGE_ENVIRONMENT=production`; keep local/test mode private. Staging rejects missing or unverifiable dependencies until later registries exist. Agents can be defined but cannot execute yet.

Review [the Phase 2 report](docs/PHASE_2_IMPLEMENTATION_REPORT.md) for every changed file and test result. `src/forge/agents/` contains registry models, schemas, lifecycle, repository, and service; `src/forge/api/registry.py` exposes the HTTP endpoints.
