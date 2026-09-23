# FORGE

FORGE is a personal project for learning and building an AI agent platform. It provides a local console for configuring agents and inspecting their model calls, tool actions, approvals, and saved results. It is under active development and is not ready for public production use.

## What works today

- Workspaces, agents, and immutable agent versions.
- OpenAI, Gemini, and a fake backend for testing without API charges.
- Queued execution, retries, cancellation, checkpoints, and follow-up conversations.
- Registered built-in tools and connected MCP tools with validation and approvals.
- Model fallback, passive availability tracking, and estimated text costs.
- Optional PDF, text, and Markdown knowledge documents, selected per agent version.

Production authentication, evaluations, release gates, and deployment/rollback management are still planned.

## Architecture

The Next.js console calls a FastAPI backend. SQLAlchemy and Alembic manage PostgreSQL, which stores configuration and durable execution records. A separate Python worker executes runs; Redis supports coordination. FORGE owns its execution loop and tool authorization. LangGraph and Qdrant are not required.

Directories: `src/forge/` contains backend modules, `web/` contains the console, `migrations/` contains database migrations, `tests/` contains backend tests, and `examples/` contains example integrations.

## Run locally

Requirements: Python 3.12+, uv, Node.js 22+, PostgreSQL 16, and Redis. Docker Compose can supply PostgreSQL and Redis; native installations also work.

```sh
uv sync --frozen --python 3.12
cp .env.example .env
```

Set the database and Redis URLs in `.env` for your installation. Use `FORGE_MODEL_BACKEND=fake` initially, and keep `FORGE_ENVIRONMENT=local` and `FORGE_EXECUTION_MODE=queued`.

```sh
# Optional: use the supplied local database/Redis containers.
docker compose up -d db redis
uv run alembic upgrade head
uv run uvicorn forge.main:create_app --factory --host 127.0.0.1 --port 8000
```

In another terminal, using the same backend configuration:

```sh
uv run python -m forge.durability.worker
```

Start the console in a third terminal:

```sh
cd web
npm ci
npm run dev
```

Open **http://127.0.0.1:3000**. Create a workspace, create an agent, save a version, and choose **Test version**. API documentation is at **http://127.0.0.1:8000/docs**. See the [console guide](web/README.md) for frontend configuration and tests.

Alternatively, `docker compose up --build --wait api` starts the containerized backend, migrations, worker, PostgreSQL, and Redis. Start the console separately. Compose defaults to the fake model backend.

## Models and tools

To use real models, configure `FORGE_MODEL_BACKEND=routed` and the server-side `FORGE_OPENAI_API_KEY` and/or `FORGE_GEMINI_API_KEY` in both API and worker environments. Choose an available provider model ID in the agent version. Restart backend processes after changing their environment. Never put API keys in frontend code or commit private environment files.

Register capabilities in **Tools**, then explicitly select their revisions on an agent version. The model may request a selected tool; FORGE validates and authorizes its execution. Customer lookup, transactions, tickets, and refunds are synthetic local demos. `inspect_python` inspects syntax without executing submitted code.

Queued runs support ordered fallback before the first successful model response. Reported costs are estimates: unknown charges stay unknown, and run budgets stop subsequent actions after observed costs reach the limit. They are not hard billing caps.

## MCP setup

For the included local code-inspection example:

```sh
uv run python examples/mcp_code_server.py
```

Configure both API and worker with:

```sh
export FORGE_MCP_SERVERS='{"code":{"url":"http://127.0.0.1:8040/mcp"}}'
```

Restart them, then use **Tools → Connect an MCP server** to discover and register capabilities. Endpoints are operator-configured; credentials stay server-side. External calls require approval. Configure `FORGE_APPROVAL_REVIEWER_TOKEN` (a random credential of at least 32 characters) and `FORGE_APPROVAL_REVIEWER_ID` (a UUID) on the API for the local reviewer flow. Keep these values private.

## Knowledge documents

Open **Knowledge**, upload a `.pdf`, `.txt`, or `.md` file, and preview keyword matches. Create or clone an agent version, select its documents, and enable **Search documents**. Documents are optional; a code-review agent can use pasted code alone.

PostgreSQL stores immutable extracted passages. Search returns up to five passages from only the selected documents. Limits: 3 MB/file, 200,000 extracted characters, 50 PDF pages, and 20 documents/version. PDFs require selectable text and no password; OCR is not included. Text and Markdown must be UTF-8. Retrieval uses English keyword matching, not semantic similarity. Documents do not generate business API integrations.

## Verification

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Integration tests require `FORGE_TEST_DATABASE_URL` and, for durability tests, `FORGE_TEST_REDIS_URL`. Use disposable test services: tests upgrade and downgrade the database schema. Never point them at your working database.

From `web/`:

```sh
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
```

GitHub Actions runs backend and frontend checks, including browser tests against a disposable backend.

## Current limitations

Organization headers select a workspace during local development; they are not authentication. Development registry routes are blocked in production mode. Keep the local interface private. External effects with an unknown outcome are not automatically replayed. Cancelling a run does not undo completed actions. Uploaded documents currently have no edit/delete UI; revised content needs a new upload and agent version.
