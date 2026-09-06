# Phase 2 implementation report

## 1. Implemented functionality

Implemented the development agent registry only: organizations, agents, immutable agent versions, lifecycle validation, organization-scoped repository/service operations, APIs, PostgreSQL migration guards, and tests. No agent execution, LangChain/LangGraph dependency, queue, evaluation engine, or production deployment behavior was added.

### Behavior

- Create an organization and read the current development organization.
- Create/list/read agents within an organization. Patch name, description, or ACTIVE/INACTIVE status; identity fields cannot be patched.
- Create/list/read v1, v2, and later immutable version snapshots. Each persists goal, instructions, model selection, fallback models, runtime template revision, limits, and dependency-reference intent. Versions start DRAFT.
- Reject empty/invalid fields, malformed limits, nonfinite/nonpositive budgets, duplicated references, extra fields, and client-supplied lifecycle status.
- Return typed JSON responses and the existing structured error envelope.
- Paginate agent/version lists with stable ordering and bounded limit/offset.
- Reject duplicate organization slugs, duplicate agent slugs within an organization, and duplicate version labels within an agent with 409. Unique constraints protect concurrent requests; these operations do not yet implement response replay via Idempotency-Key.
- Use parent-agent row locks for version creation and version row locks for lifecycle changes. Services own commit/rollback.
- Archive permitted lifecycle states without changing configuration. Reject invalid/repeated transitions. Later promotion/evaluation edges are defined but not exposed as endpoints.
- Guard history in PostgreSQL: DRAFT-only insertion, configuration immutability, valid lifecycle edges, and rejection of DELETE/TRUNCATE. Schema administrators can deliberately override database protections; the guard is for ordinary writes.

### Explicit phase boundaries

1. **Access is development-only.** `X-Organization-ID` chooses the local/test context, not an authenticated identity. Repository queries constrain access to that context and conceal cross-organization IDs. All registry routes fail with 503 `REGISTRY_AUTH_REQUIRED` in production until membership authentication is implemented. Health endpoints remain available.
2. **Staging cannot succeed yet.** A missing evaluation suite returns `EVALUATION_SUITE_REQUIRED`; supplied but unverifiable references return `STAGING_DEPENDENCIES_UNAVAILABLE`. No lifecycle update is committed. The relevant tool/policy/model/evaluation registries arrive later.
3. **Draft references are intent.** Tool/policy UUID arrays and the evaluation-suite UUID are immutable snapshots, not yet foreign keys to future tables. Later validated/normalized bindings must agree with those IDs.
4. **No runtime dependency added.** LangChain/LangGraph execution remains Phase 3 onward.

## 2. Every file changed

### New application files

| File | Purpose / relationships |
| --- | --- |
| `src/forge/agents/__init__.py` | Package marker |
| `src/forge/agents/schemas.py` | Pydantic request/response validation; consumed by API and services |
| `src/forge/agents/lifecycle.py` | State enum and allowed transitions; called by service |
| `src/forge/agents/models.py` | SQLAlchemy organization/agent/version tables; used by repository and Alembic metadata |
| `src/forge/agents/repository.py` | Scoped reads, row locks, entity insertion; called by service |
| `src/forge/agents/service.py` | Domain validation, uniqueness error mapping, transaction commits, immutable version creation, archive/staging decisions |
| `src/forge/api/registry.py` | Development access/scope dependencies and thin HTTP routes calling service |

### New migration and tests

| File | Purpose |
| --- | --- |
| `migrations/versions/0002_agent_registry.py` | Three domain tables, constraints, immutable-history/lifecycle trigger function, downgrade |
| `tests/test_registry_validation.py` | Configuration/patch validation, lifecycle rules, production access block |
| `tests/test_registry_postgres.py` | Actual API/database tests for history, scoping, uniqueness, staging, concurrency, SQL guards |

### Existing application/test files changed

| File | Change |
| --- | --- |
| `src/forge/main.py` | Register registry router under `/api/v1` |
| `migrations/env.py` | Load registry models into Alembic target metadata |
| `tests/test_postgres.py` | Migration round-trip expected head becomes `0002_agent_registry` |

### Documentation changed

| File | Change |
| --- | --- |
| `forge.md/03_AGENT_DEFINITION_AND_REGISTRY.md` | Concrete Phase 2 lifecycle, editable fields, staging limits, development scope |
| `forge.md/07_DATABASE_SCHEMA.md` | Actual organization schema and version configuration additions; migration guards |
| `forge.md/08_API_CONTRACT.md` | Organization bootstrap/current routes, headers, request example, pagination, errors and limits |
| `forge.md/12_ARCHITECTURE_DECISIONS.md` | Record Phase 2 access/staging boundaries |
| `README.md` | Current implementation status and registry walkthrough |
| `docs/CODE_REVIEW_GUIDE.md` | Phase 2 directory/file reading order and version-creation call path |
| `docs/PHASE_2_IMPLEMENTATION_REPORT.md` | This new session report |

New source directory: `src/forge/agents/`. Existing directories touched: `src/forge/api/`, `src/forge/`, `migrations/`, `migrations/versions/`, `tests/`, `forge.md/`, `docs/`, and root README. No dependency, configuration, Docker, CI, or lockfile change was required.

## 3. Migration added

Revision `0002_agent_registry`, parent `0001_foundation`:

- Creates organizations, agents, agent_versions with UUID primary keys, appropriate foreign keys, uniqueness, timestamps, JSONB configuration, and status constraints.
- Adds `forge_guard_agent_version()` and row/statement triggers.
- Compares whole-row JSON excluding lifecycle status to prevent configuration/history edits, including combined configuration-and-status edits.
- Rejects inserts into non-DRAFT lifecycle and invalid lifecycle edges.
- Rejects version DELETE and TRUNCATE.
- Downgrade drops the new tables and function. This is destructive; tests use the disposable local database.

Generated the initial migration with Alembic, reviewed/extended it with trigger SQL, then renamed it to `0002_agent_registry.py`. The database revision identifier stayed the same. Only the disposable test database was migrated during this session.

## 4. Tests added

26 new test cases after parameter expansion, for 38 total:

- 12 invalid version configurations.
- 5 invalid metadata patches.
- Lifecycle allowed/blocked examples.
- Registry rejection in production without membership authentication.
- v1/v2 creation, pagination, agent metadata independence, immutable version PATCH, archive and repeated-archive rejection.
- Organization scoping across agent/version reads/writes, wrong-parent version access, missing/invalid headers, invalid pagination, unknown organization.
- Duplicate agent/version handling and inactive-agent behavior.
- Unverified staging references remain DRAFT.
- Concurrent duplicate version creation yields one 201 and one 409; concurrent archive yields one 200 and one 409.
- Direct SQL configuration update, deletion, truncation, and illegal lifecycle transition are blocked without changing history.
- Organization uniqueness and rejection of client-supplied APPROVED status.

Existing migration test upgrades, downgrades to base, re-upgrades to current head, and checks schema drift. The tests require a disposable database; absence of `FORGE_TEST_DATABASE_URL` explicitly skips database-dependent cases.

## 5. Commands run

Grouped by purpose; repeated checks are consolidated.

### Inspection / implementation

Read relevant specs, existing database/error/configuration code, migration environment, main app, and integration tests using `cat`; searched local instructions with `rg --files -g AGENTS.md` (none found). Consulted primary SQLAlchemy/PostgreSQL documentation linked below. Created the `agents` package and files using `/tmp/forge_registry.py`, shell heredocs, and targeted Python edits. No new package installation.

### PostgreSQL and migration

```sh
/opt/homebrew/opt/postgresql@16/bin/pg_ctl -D .tools/pgdata -l .tools/postgres.log -o '-h 127.0.0.1 -p 55432' start
FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_test .tools/bin/uv run alembic revision --autogenerate -m agent_registry --rev-id 0002_agent_registry
mv migrations/versions/0002_agent_registry_agent_registry.py migrations/versions/0002_agent_registry.py
FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_test .tools/bin/uv run alembic check
FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_test .tools/bin/uv run alembic current
```

Tests invoked Alembic upgrade head, downgrade base, upgrade head, and check as subprocesses. The registry test fixture also ensures the head migration exists.

### Verification

```sh
.tools/bin/uv run ruff check . --fix
.tools/bin/uv run ruff format .
.tools/bin/uv run ruff check .
.tools/bin/uv run ruff format --check .
FORGE_TEST_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_test .tools/bin/uv run pytest -q
.tools/bin/uv build
```

Initial lint found generated migration formatting and long SQL lines; formatted Python and split SQL conditions. Tests passed on the first execution. Added one final test for organization uniqueness/initial lifecycle rejection and reran the complete suite.

### HTTP smoke test and cleanup

```sh
FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_test .tools/bin/uv run uvicorn forge.main:create_app --factory --host 127.0.0.1 --port 58000
```

Ran `.tools/bin/uv run python` with an HTTPX script against that real listener: create organization → create agent → create v1/v2 → list history → retrieve OpenAPI. Assertions passed for 201 creation and 200 list/OpenAPI responses. Stopped Uvicorn with Ctrl-C; shutdown completed.

```sh
/opt/homebrew/opt/postgresql@16/bin/pg_ctl -D .tools/pgdata stop -m fast
```

Temporary processes are stopped. Test records remain only in the ignored disposable cluster. Generated build/test/lint caches and `dist/` artifacts were refreshed. No Git commit, push, hosted CI, Docker execution, or deployment occurred. Finally checked Markdown links/code fences and lint after documentation updates.

## 6. Results

| Check | Result |
| --- | --- |
| Complete tests with real PostgreSQL | **38 passed**, 2 existing upstream deprecation warnings |
| Ruff lint / formatting | Passed |
| Migration round trip | Passed |
| Migration current | `0002_agent_registry (head)` |
| Alembic metadata drift | No new upgrade operations detected |
| Direct SQL history guards | Passed |
| Concurrent create/archive requests | Passed |
| Live HTTP registry and OpenAPI | Passed |
| Source/wheel package build | Passed |
| Docker / hosted CI | Not run; previous environment limits remain |

Warnings are the existing Starlette HTTPX/AnyIO deprecations. No warnings were suppressed.

## 7. Unresolved issues / review limits

Production registry access is deliberately unavailable until authentication/membership exists. Header scoping is not production authorization. Staging is deliberately blocked until all required references can be validated. Runtime/provider execution and release services do not exist yet. Registry creation uses natural-key uniqueness, not an Idempotency-Key response cache. These boundaries are reflected in current specs/API docs.

The migration uses PostgreSQL-specific triggers; SQLite is not a substitute for its tests. Future schema changes must preserve the immutability guard. Framework/database administrator privileges are outside these application guards.

## 8. Recommended next step and review path

Review schemas → lifecycle → models → repository → service → routes → migration → tests, using `CODE_REVIEW_GUIDE.md`. Start with creating v1/v2 in `/docs` and observe that editing the parent agent cannot change their configuration.

After review, Phase 3 is next upon instruction: LangChain `create_agent` on LangGraph, a thin Gemini integration, exact-version runs/events, and deterministic fake-model tests. No Phase 3 work was started.

## Primary references

Row-lock/session patterns were checked against [SQLAlchemy 2.0 session documentation](https://docs.sqlalchemy.org/en/20/orm/session_api.html). PostgreSQL's [trigger function documentation](https://www.postgresql.org/docs/16/plpgsql-trigger.html) supports the history-guard implementation. The concrete lifecycle/access choices are FORGE decisions recorded in the specifications.
