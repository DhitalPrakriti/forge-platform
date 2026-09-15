# Code-review conversations and formatted output

## Delivered

- Safe Markdown/GFM output: headings, lists, emphasis, inline code, indented fenced code, and tables. Raw HTML is disabled, default link sanitization retained, remote images disabled. Existing saved outputs render without another model call.
- Completed runs offer a follow-up composer. Earlier messages/replies appear in a history panel with a previous-turn link. Each new turn retains the same immutable version and tools, with its own run evidence and idempotency key.
- Parent scope/completion/version validation occurs server-side. Client-supplied history is not accepted. At most 10 prior turns and 60,000 history characters; limits fail explicitly instead of silent truncation. History persists in PostgreSQL execution configuration and survives worker dispatch/retry/approval continuation.
- Gemini and OpenAI receive prior user/assistant text using their native message roles. Prior tool effects are not replayed or automatically authorized. Full prior tool payloads/private reasoning are not conversation memory.
- Installed `inspect_python` tool reports syntax validity, functions, classes, imports, and division line numbers. Input capped at 12,000 characters. Uses AST parsing only: no execution, imports, shell, filesystem access, or code-writing. Uses existing version bindings, policy/Tool Hub validation, recording, and local recovery path with a distinct LOCAL_STATIC_V1 handler.

## Files and responsibilities

Backend:
- `runtime/schemas.py`: optional parent run ID.
- `runtime/service.py`: parent validation, bounded saved history, idempotency input, per-turn request.
- `model_router/base.py`: private-repr request history field.
- `model_router/gemini.py`, `model_router/openai.py`: provider-native text history.
- `durability/engine.py`, `approvals/service.py`: restore history during execution/continuation.
- `durability/service.py`: preserve parent when retrying a failed turn.
- `tools/python_inspection.py`: bounded AST tool input/output schema and implementation.
- `tools/builtins.py`: installed definition and dispatch.
- `tools/policy.py`, `tools/hub.py`: explicitly recognize static local handler for validation/recovery.
- `tools/schemas.py`: registerable tool name.

Frontend:
- `components/ui/markdown-output.tsx`: reusable safe renderer.
- `components/runs/follow-up.tsx`: composer with retained request/key on uncertain response.
- `components/runs/run-detail-screen.tsx`: formatted output, earlier messages, previous-turn link, composer.
- `components/runs/playground-screen.tsx`: updated conversation/provider guidance.
- `components/tools/tools-screen.tsx`: accurate installed-tool copy.
- `lib/api/types.ts`: parent request field and Python tool name.
- `lib/tool-demo.ts`: registration card and fake-mode inspection example.
- `app/globals.css`: readable Markdown and conversation styling.
- `package.json`, `package-lock.json`: exact react-markdown and remark-gfm versions with resolved dependencies. Added to safely parse Markdown/GFM rather than building a custom parser. npm reported no vulnerabilities at installation.

Tests:
- `tests/test_python_inspection.py`: valid structure and syntax failure without execution.
- `tests/test_runtime_postgres.py`: stored context, idempotent follow-up, cross-organization rejection.
- `tests/test_durability_postgres.py`: real Tool Hub inspection then follow-up dispatch with tool bindings and prior context.
- `tests/test_runtime.py`: Gemini request contract now uses typed message lists.
- `web/tests/markdown-output.test.tsx`: formatting, code whitespace, HTML/image/executable-link rejection.
- `web/tests/e2e/console.spec.ts`: follow-up/history/parent-link/mobile overflow journey.

Documentation: `forge.md/FORGE_FRONTEND_SPEC.md`, `forge.md/08_API_CONTRACT.md`, `docs/CODE_REVIEW_GUIDE.md`, and this report record the explicitly authorized extension and review path.

## Verification and commands

- `uv run ruff check src tests`, targeted `ruff format`: passed after formatting changes.
- Full PostgreSQL/Redis suite: 126 passed initially; seven Gemini tests expected the old string prompt format. Updated those assertions for typed messages; all seven passed. One additional worker tool/conversation test passed. Total 134 Python scenarios passed across runs.
- `npm run typecheck`, `npm run lint`, `npm run format:check`, `npm run build`: passed.
- `npm test`: 17 passed including the two new Markdown tests.
- `npm run test:e2e`: eight existing scenarios passed against an isolated fake API on 8001 using disposable forge_test_utf8 and Redis database 1.
- `npm run test:e2e -- --grep 'follow-up conversation'`: new ninth scenario passed.
- Visually inspected the user's saved Gemini response after Markdown rendering in Chromium; headings, lists and code indentation render correctly. No new provider call needed.
- Restarted live routed API and worker with existing private configuration. Frontend remains at localhost:3000.

No migrations. No provider keys in changes. No paid calls made for this session. User edits in `.env.example`, `src/forge/db/session.py`, and generated frontend files were excluded from the commit.

## How to use

Refresh the completed run to see formatted output and Send follow-up. To add Python inspection: Tools → Register inspect_python → agent version → Clone version → select inspect_python → instruct the agent to call it for Python snippets → save. Test: “Use inspect_python on this function, explain its findings, and suggest a fix.” Paste code, run, and inspect the tool-call record. Ask another question with Send follow-up.

For another provider, clone a version with an exact available OpenAI model ID. Each conversation remains pinned to its version/provider; mid-conversation model switching is not implemented. Provider routing is available for both, but this session did not verify OpenAI account generation access.

## Limits

No arbitrary Python execution or full security/static-analysis certification. No automatic edits to local project files. No server-wide conversation list or cross-device organization discovery. Follow-up navigation opens a new run inspector rather than a streaming chat window. Cost accounting, hard budgets, fallback, and circuit breakers remain unfinished Phase 7 work. Local console authentication remains unsuitable for public deployment.
