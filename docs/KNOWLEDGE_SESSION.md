# Optional workspace knowledge — 2026-09-22

## Result

PDF, UTF-8 text and Markdown documents can now be uploaded through Knowledge. PostgreSQL stores immutable source metadata and extracted passages. Preview keyword search without calling an LLM; select up to 20 document snapshots on a new agent version and enable `search_documents`. Tool Hub derives permitted documents from the saved run configuration, validates the request, checks policy and records source excerpts as tool-call evidence. Existing versions default to no documents. No real provider calls were made during verification.

FORGE has both a control plane (workspace/agent/version/tool configuration) and an execution backend (model routing, worker, tools, approvals, saved results). The local setup uses PostgreSQL on 55432 and Redis on 56379 as native processes, with Next.js on 3000, FastAPI on 8000 and a separate Python worker. Docker is an alternative packaging option, not a requirement for these running services. There is no Qdrant or LangGraph dependency. Separate workspaces are logically scoped in the same database; they do not need separate containers.

Knowledge and business tools are distinct: a restaurant handbook can answer opening-hour questions through this generic search capability. A reservation still needs a connected booking API/MCP tool. Uploaded text does not create executable functions. Code review can work without documents, or optionally use a team's coding standards.

## Every changed file and directory

| Files | Responsibility / caller and callee |
| --- | --- |
| `src/forge/knowledge/__init__.py` | New domain package. |
| `src/forge/knowledge/schemas.py` | Bounded upload, public metadata, preview search, strict model tool input/output contracts. |
| `src/forge/knowledge/models.py` | SQLAlchemy document/chunk records used by service and Alembic metadata. |
| `src/forge/knowledge/extraction.py` | Upload decoding, type/size/UTF-8 validation, PDF subprocess orchestration, deterministic overlapping passages. Called by knowledge service. |
| `src/forge/knowledge/pdf_extract.py` | Isolated PDF extraction entry point; refuses encrypted/oversized documents, emits page text only. Called by extraction subprocess. |
| `src/forge/knowledge/service.py` | Organization checks, immutable upload transaction, exact document resolution and bounded PostgreSQL search. Called by API, registry, run admission and Tool Hub. |
| `src/forge/api/knowledge.py` | Development-only routes; bounds raw upload before JSON parsing; delegates to service. |
| `src/forge/main.py` | Includes knowledge router under `/api/v1`. |
| `src/forge/agents/models.py`, `schemas.py` | Optional default-empty document UUID bindings on immutable versions; maximum 20, no duplicate bindings. |
| `src/forge/agents/service.py` | Validates same-workspace documents and requires the search tool when documents are selected. |
| `src/forge/runtime/service.py` | Revalidates document availability at admission and snapshots bindings into run configuration. |
| `src/forge/tools/builtins.py`, `schemas.py` | Registers installed `search_documents` metadata/strict schema under the existing tool registration API. |
| `src/forge/tools/hub.py`, `policy.py` | Allows the known read-only knowledge handler through existing metadata/policy checks; dispatches with server-owned document bindings; records validated results. |
| `migrations/env.py` | Registers knowledge metadata. |
| `migrations/versions/0009_knowledge.py` | New tables, organization index, unique passage positions, version column, immutable update/delete/truncate guards. |
| `pyproject.toml`, `uv.lock` | Adds pypdf >=6.18.1,<7, resolved/locked to 6.19.0. No embedding dependency. |
| `web/app/knowledge/page.tsx` | New route delegates to KnowledgeScreen. |
| `web/components/knowledge/knowledge-screen.tsx` | Workspace-keyed upload and search preview; bounded file reading; visible limits/errors/sources. |
| `web/components/knowledge/document-picker.tsx` | Shared paginated selection, technical metadata and explicit refresh/clear controls. |
| `web/components/agents/version-form.tsx` | Clone/preserve document bindings, select snapshots, explicitly register/select search tool. |
| `web/components/layout/app-shell.tsx` | Knowledge navigation. |
| `web/components/tools/tool-catalog.tsx` | Adds Knowledge category. |
| `web/lib/tool-demo.ts`, `tool-presentation.ts` | Installed-tool label/guidance and deterministic fake search command. |
| `web/lib/api/forge.ts`, `types.ts`, `web/lib/schemas.ts` | Typed upload/list/search calls and optional version document bindings. |
| `web/app/api/forge/[...path]/route.ts` | Explicit knowledge route allowlist; upload body capped before proxy buffering. |
| `tests/test_knowledge.py` | PDF/text/Markdown extraction and malformed/encrypted/blank/oversized/non-UTF-8/path rejection. |
| `tests/test_knowledge_postgres.py` | Workspace isolation, immutable text, required tool bindings, run evidence, zero-document access, model ID injection denial and cross-workspace version rejection. |
| `tests/test_postgres.py` | Migration head expectation; existing upgrade/downgrade/metadata checks include 0009. |
| `web/tests/e2e/console.spec.ts` | Upload → preview → version binding → actual Tool Hub retrieval in a fake-model run. |
| `README.md` | Setup, usage and limits. |
| `forge.md/12_ARCHITECTURE_DECISIONS.md`, `FORGE_FRONTEND_SPEC.md` | Records user-requested optional knowledge scope and supported UI. |
| `docs/CODE_REVIEW_GUIDE.md`, this file | Reading order, file map, verification, limits and review questions. |

Existing unrelated changes in `.env.example`, `src/forge/db/session.py`, generated Next files and untracked local instruction files are excluded from the feature commit. Credentials and local database backup remain ignored.

## Migration and data handling

Migration 0009 adds `knowledge_documents`, `knowledge_chunks` and `agent_versions.knowledge_document_ids` with default `[]`. Existing agent-version immutability guards also protect this new field. New uploads create separate identities; there is no update or delete endpoint. Original binary files are discarded after extraction; metadata includes their SHA-256 hash. A backup of the live local database was saved to ignored `.tools/before-knowledge-20260922.dump` before upgrading. No local workspace was reset.

## Verification / commands

- `.tools/bin/uv add 'pypdf>=6.18.1,<7'`
- `.tools/bin/uv run ruff check src tests migrations` — passed.
- Targeted Ruff formatting and Prettier formatting on changed code.
- `FORGE_TEST_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_test_utf8 FORGE_TEST_REDIS_URL=redis://127.0.0.1:56379/1 .tools/bin/uv run pytest -q` — **182 passed**, two existing Starlette deprecation warnings. Disposable test database only; migration upgrade/downgrade and Alembic check pass.
- From `web`, with Homebrew Node22 on PATH: `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build` — passed; **24 unit tests**.
- `FORGE_API_URL=http://127.0.0.1:8001 FORGE_TEST_MCP_SERVER=code npm run test:e2e` with test API/worker, fake model and local reviewer/MCP configuration — **12 passed**, no skips. Includes existing refund/MCP approval, fallback cloning, history and new knowledge scenario. Also tested knowledge alone on inline backend.
- Inspected the generated Knowledge screenshot from the browser test.
- Live local database backup, `alembic upgrade head`, API and worker restart with existing provider/reviewer/MCP environment.
- Live readiness returns 200; `/knowledge` returns 200; Forge Development still resolves with its existing UUID and an initially empty document list. No example documents were inserted into the user's workspace.

An initial PDF check caught macOS rejecting RLIMIT_AS; memory limits now apply on Linux only, with CPU/wall-time limits on macOS. The access-denial test expectation was corrected from FAILED to the existing DENIED status. Both reran successfully.

## Limits / unresolved scope

- English PostgreSQL full-text keyword matching, not embedding/semantic retrieval. Search can miss synonyms; no matches is not proof information is absent. Five ranked passages, at most 1,200 characters each; 200-character overlap.
- Up to 3 MB per upload, 200,000 extracted characters, 50 PDF pages and 20 documents per agent version. Uploads run synchronously, with 15-second PDF wall timeout and 10-second subprocess CPU limit. Linux caps subprocess virtual memory at 2 GiB; macOS has no equivalent memory cap here. This is not a general hostile-file sandbox or a production multi-user ingestion service.
- PDFs need selectable text. No OCR, image understanding, table reconstruction guarantees or encrypted PDF support. Parser limitations are described in [pypdf extraction documentation](https://pypdf.readthedocs.io/en/6.18.1/user/extract-text.html).
- No edit/delete/retention controls, duplicate-upload deduplication, bulk ingestion, external document connectors or original-file download. Upload revised content and clone a version to change its references.
- Document excerpts are untrusted data; tool guidance requests citations. Authorization is enforced by FORGE regardless of model behavior, but this does not guarantee every generated answer is grounded or correctly cited.
- Workspace headers remain local-development scoping, not production authentication. Existing production guard remains in place.
- Backend upload uses bounded JSON containing base64 file content, not multipart; console provides the file chooser. Automatic OpenAPI upload form generation is not provided by this streaming route.

## Recommended reading order and walkthrough

1. `knowledge/schemas.py` and `models.py` — contracts and durable records.
2. `extraction.py`, then `pdf_extract.py` — file validation and parsing limits.
3. `knowledge/service.py` — scoped retrieval and transaction.
4. Migration 0009 — durability and immutable source text.
5. Registry and runtime service additions — bind exact documents and snapshot them.
6. Tool Hub dispatch — query comes from the model, accessible IDs come from the saved run.
7. Knowledge screen, shared picker, version form and API proxy.
8. Tests before exercising the real providers.

Concrete request: upload `restaurant.md` containing Monday opening hours → service extracts passages and commits a new document UUID → select it on a new version and enable Search documents → run admission snapshots the selected UUID → model requests `search_documents({"query":"opening hours"})` → Tool Hub checks registered revision/schema/policy → knowledge service searches only that UUID within the run's organization → result contains title, passage and excerpt → recorded tool result returns to the model for an answer. Booking a table still requires a separate booking tool.

Review questions: Why do documents remain optional? Why doesn't an upload alter an old version? Where are model-provided document IDs rejected? What distinguishes a PDF page number from a text passage number? Why does a free search preview differ from a paid model run? What would semantic retrieval and production authentication need next?

Recommended next step: upload a small handbook in Forge Development, preview keywords, clone an agent with the search capability, and ask a source-grounded question. Do not begin another phase automatically.
