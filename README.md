# FORGE

FORGE is a production control plane for AI agents. The source of truth is [the specification pack](forge.md/00_INDEX.md). Phases 1–6 are implemented: registry, model/tool execution, refund approvals, and durable queued workers with recovery, retries, cancellation, and timeout.

## Included

FastAPI application factory, Pydantic Settings, SQLAlchemy 2.x async PostgreSQL connections/sessions, Alembic baseline, health endpoints, structured errors, tests, Ruff, locked dependencies, Docker Compose, and GitHub Actions CI.

The new [local web console](web/README.md) supports workspace setup, agents, immutable versions, test runs, and execution inspection. It uses the Phase 6 API with demo tool registration, binding, and call inspection; future staging/evaluation/deployment screens are not implemented.

## Web console — easier local testing

Keep PostgreSQL, Redis, the worker, and the migrated API running. The API listens on `127.0.0.1:8000`. To test without a provider key, use `FORGE_MODEL_BACKEND=fake` for both API and worker. New runs return QUEUED and execute in the worker.

With Node.js 22 installed, open another terminal:

```sh
cd web
npm ci
npm run dev
```

Open **http://127.0.0.1:3000**. Create a workspace or connect an existing organization UUID once. Then create an agent, save a version, and select **Test version**. The console supplies the organization header and run idempotency key automatically.

On this Mac, Node was installed with `brew install node@22`. If `node` is not on your terminal's PATH, run `export PATH="/opt/homebrew/opt/node@22/bin:$PATH"` first.

See [the frontend session report](docs/FRONTEND_LOCAL_CONSOLE_SESSION.md) for every new file, test results, limitations, and a request walkthrough. No provider secrets belong in `web/`.

## Local setup

Install Python 3.12+ and uv (the lockfile was generated with uv 0.12.10). A workspace-local uv bootstrap is available at `.tools/bin/uv` on the development machine; substitute that for `uv` if it is not on PATH.

```sh
uv sync --frozen --python 3.12
cp .env.example .env
```

Start PostgreSQL 16, creating the database/user specified in `.env`. With Docker installed:

```sh
docker compose up -d db redis
uv run alembic upgrade head
uv run uvicorn forge.main:create_app --factory --reload
# In another terminal using the same .env:
uv run python -m forge.durability.worker
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

Compose waits for PostgreSQL/Redis health, runs a one-shot migration, and starts the API plus worker as non-root container users. Compose defaults to fake mode. Credentials in Compose and `.env.example` are local examples. Supply production secrets externally; never commit `.env`. No production deployment has been configured or performed.

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

PostgreSQL integration tests skip unless `FORGE_TEST_DATABASE_URL` is set. Durability tests also require `FORGE_TEST_REDIS_URL` pointing to disposable Redis. It upgrades and downgrades the schema: use a disposable database only.

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

Organization, agent, and immutable version tables are implemented. Gemini and a labelled fake backend support initial execution. Durable queue/Redis workers and the local console are implemented. Provider fallback, production authentication, evaluations, and the full dashboard remain in later phases.

## Architecture direction and session reviews

Agent execution will use a FORGE-owned runtime and state machine with provider adapters. See [runtime design](forge.md/14_FORGE_RUNTIME_DECISION.md). PostgreSQL stores durable checkpoints; LangChain/LangGraph and graph databases are not required. Current implementation includes Phase 6 durable model/tool execution and persistent approval continuation.

Start each code review with [the directory and walkthrough guide](docs/CODE_REVIEW_GUIDE.md). Session reports explain each changed file, its purpose, validation results, and limitations.


## Phase 2: review the registry

Apply `uv run alembic upgrade head`, then use `/docs` to:

1. `POST /api/v1/organizations` with a name and slug; copy the returned UUID.
2. Supply that UUID as `X-Organization-ID` for registry requests.
3. `POST /api/v1/agents` with name, slug, and optional description.
4. Create v1 and v2 using `POST /api/v1/agents/{agent_id}/versions`; see the exact body in [the API contract](forge.md/08_API_CONTRACT.md).
5. List/read the versions, change agent metadata, and verify historical configuration is unchanged.
6. Archive a DRAFT version. Editing its configuration returns `VERSION_IMMUTABLE`.

The organization header is a development selector, **not authentication**. Registry routes are disabled when `FORGE_ENVIRONMENT=production`; keep local/test mode private. Staging rejects missing or unverifiable dependencies until later registries exist. Agents can now execute through the Phase 3 endpoint described below.

Review [the Phase 2 report](docs/PHASE_2_IMPLEMENTATION_REPORT.md) for every changed file and test result. `src/forge/agents/` contains registry models, schemas, lifecycle, repository, and service; `src/forge/api/registry.py` exposes the HTTP endpoints.


## Phase 3: run an exact version

Use a UTF-8 PostgreSQL database and apply `uv run alembic upgrade head` before starting the updated API. Provider configuration:

| Variable | Behavior |
| --- | --- |
| `FORGE_MODEL_BACKEND` | `gemini` (default) or explicitly labelled `fake` demo |
| `FORGE_GEMINI_API_KEY` | Server-side Gemini key; never enter it into Swagger or commit it |
| `FORGE_MODEL_TIMEOUT_SECONDS` | Model wait timeout, default 60; also bounded by version runtime limit |
| `FORGE_MODEL_MAX_OUTPUT_TOKENS` | Output cap, default 1024 |

For a local demo without a key or charges:

```sh
FORGE_MODEL_BACKEND=fake uv run uvicorn forge.main:create_app --factory --host 127.0.0.1 --port 8000
```

Create a version with standard-agent-v1, no tools/policies/fallbacks, and DRAFT status. Open `/docs` → **runs → POST /api/v1/runs**. Enter your organization ID and an Idempotency-Key such as `my-first-run`, then provide the actual version ID and input message. A new run returns 201; inspect its `status` and `output`. Reusing the same key/body returns the existing run without calling the model again. Use a new key for a deliberately new execution.

Read the saved run, events, and model calls through the three GET endpoints. Fake output includes `FAKE MODEL` identification and provider `fake`. To use Gemini, configure your key privately in `.env` or environment, choose backend `gemini`, and restart the API. A real invocation sends the selected version's goal/instructions and your input to Google and may incur charges. No key was configured for this session's tests; Gemini network execution remains unverified.

The original Phase 3 milestone made one model call; Phase 4 now supports registered and permitted demo tools, as described below. Real dollar costs are null and budget enforcement is not implemented until Phase 7. A crash or lost final database write can leave a RUNNING record; idempotency returns it instead of attempting automatic recovery. Production access remains disabled.

For side-by-side function explanations and all file changes, read [the Phase 3 report](docs/PHASE_3_IMPLEMENTATION_REPORT.md) and [review guide](docs/CODE_REVIEW_GUIDE.md).

## Phase 4: model-requested tool calling

Apply `uv run alembic upgrade head` to add the Tool Hub tables, then restart the API. No new dependencies or provider key are needed for fake mode.

In the console, open **Tools** and register the demos. Clone an existing agent version, give it a new label, and select tools under **Tool permissions**. Save it, click **Test version**, and expand **Fake-backend tool examples**. **Customer lookup** fills:

```text
/tool lookup_customer {"customer_id":"cust_001"}
```

Press **Run agent**. Expect two model calls and one tool call, with normalized arguments, ALLOW/DENY decision, exact revision ID, latency, and result in the inspector. `lookup_transactions` reads synthetic transactions; `create_ticket` creates a local database ticket. It does not send an external message or create a real helpdesk ticket. Selecting no tools on a version makes these requests fail closed.

The Gemini adapter can request the same schema-defined tools with automatic SDK execution disabled; only FORGE's Tool Hub can execute them. Real Gemini execution still needs a backend key and a supported model; it was not live-tested in this phase. Refund policies/approvals remain Phase 5, worker recovery Phase 6, monetary accounting/enforcement Phase 7.

See [the Phase 4 report](docs/PHASE_4_IMPLEMENTATION_REPORT.md) for every changed file, migration, commands, test results, and a function-by-function walkthrough.


## Phase 5: simulated refunds and approval

In Tool Hub, register `issue_refund` and **Register refund policy**. Clone a version, select both revisions, and save. For comfortable review, use a runtime limit such as 600 seconds; approval waiting consumes that limit.

Test with `/tool issue_refund {"customer_id":"cust_001","amount_usd":"425.00"}`. USD 50.00 allows automatically, 425.00 waits for approval, and 700.00 denies. These are local demo rows; no money moves.

Configure `FORGE_APPROVAL_REVIEWER_TOKEN` (random, at least 32 characters) and `FORGE_APPROVAL_REVIEWER_ID` (UUID) on the API. For this local session, an ignored, permission-600 `.tools/local-reviewer.env` was created and loaded into the API. Open that file locally and copy just the token value into **Local reviewer credential** on the run page. Enter a reason, confirm **Approve refund**, then **Resume approved run**. The token is not saved in browser storage. Never commit the credential file.

The saved decision and checkpoint survive an API restart. Repeated resume never creates another refund after completion. General execution-crash recovery, scheduled expiry, queue workers, production IAM, and real payments are outside this phase. See [the complete Phase 5 review](docs/PHASE_5_IMPLEMENTATION_REPORT.md).


## Phase 6: durable worker execution

New runs return **202 Accepted / QUEUED** and the inspector polls saved progress. Approval schedules worker continuation automatically. **Cancel run** requests a stop at the next safe boundary; it does not undo completed effects. **Retry as new run** creates a linked execution only when the server can rule out a successful/unknown side effect.

The worker entry point is `uv run python -m forge.durability.worker`. Configure the same database, Redis URL, provider, and provider credential as the API. PostgreSQL owns dispatch/checkpoints; Redis notifications can be lost without losing work. Do not use transaction-pooled database connections for the worker: its advisory lock requires a pinned PostgreSQL session.

Current Mac processes use PostgreSQL on 55432, Redis on 56379, API on 8000, and web on 3000. Redis was installed with Homebrew and launched on loopback without automatic login startup. In each backend terminal set `FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_local`, `FORGE_REDIS_URL=redis://127.0.0.1:56379/0`, and `FORGE_MODEL_BACKEND=fake`. For the API, also source ignored `.tools/local-reviewer.env` for approval credentials. Default execution mode is queued; explicit inline mode retains legacy development behavior without worker recovery.

An interrupted model request can be retried with uncertain usage/charges; saved responses and committed local effects are reused. External side-effect integrations and cost enforcement remain later work. See [Phase 6 report](docs/PHASE_6_IMPLEMENTATION_REPORT.md) for every file, crash tests, commands, and limitations.
