# MCP tools: setup and review

Session: 2026-09-16. User-authorized extension of the Tool Hub; this does not complete the remaining Phase 7 model fallback, health, circuit breaker, or cost-accounting work.

## What works

Tools → choose a configured MCP server → Discover tools → review descriptions and schemas → register selected tools → clone an agent version and select their exact revisions → run with Gemini or OpenAI → review the exact requested arguments → approve or deny → inspect the saved tool result and model reply.

The model chooses among tools explicitly bound to that version. It does not invent an implementation or grant itself permissions. The same MCP tools work through either existing provider adapter. No LangGraph or LangChain was added.

All MCP calls require the existing authenticated local reviewer, regardless of server-provided risk/read-only annotations. These annotations are untrusted. Approval is bound to the exact tool ID and normalized argument hash. Registration installs an internal `mcp-review` policy automatically; it is not an agent-selectable refund policy.

## Try the local code-review server

From the repository root, run in its own terminal:

```sh
.tools/bin/uv run python examples/mcp_code_server.py
```

This starts Streamable HTTP at `http://127.0.0.1:8040/mcp`. Its `inspect_code` tool parses pasted Python and returns syntax, function, import, and division information. It never executes pasted code or reads your files. This is a separate MCP server, not a fake transport.

Before starting **both** the API and worker, load their existing database/provider configuration and add:

```sh
export FORGE_MCP_SERVERS='{"code":{"url":"http://127.0.0.1:8040/mcp"}}'
```

The API also needs your existing `.tools/local-reviewer.env` loaded. No API key is needed for this local MCP server. Existing Gemini/OpenAI calls retain their normal provider billing.

1. Open Tools and choose `code`.
2. Click **Discover tools** and inspect the schema.
3. Click **Register inspect_code**.
4. Clone your code-review agent version; select the new `mcp_…_inspect_code` tool under Tool permissions.
5. Set the model to your working Gemini or OpenAI model and save the immutable version.
6. In the playground, write: “Use inspect_code to check this Python, then explain the problem: `def average(xs): return sum(xs) / len(xs)`”.
7. When it requests the tool, inspect the payload under **Tool approvals**. Enter your existing local reviewer credential and a reason, then approve. The queued worker continues automatically.

A model may answer without requesting a tool. To test the transport deterministically with the fake backend, use `/tool <registered-tool-name> {"code":"x = 1"}`. The model is fake in that test; the MCP call is real and still requires approval.

## Connect another server without writing a tool implementation

An operator adds the server's exact Streamable HTTP URL to the same JSON setting on the API and worker. Optional bearer tokens stay in the server environment:

```sh
export FORGE_MCP_SERVERS='{"code":{"url":"http://127.0.0.1:8040/mcp"},"my_service":{"url":"https://your-server.example/mcp","token":"REPLACE_LOCALLY"}}'
```

Use an ignored, permission-restricted env file for real credentials; never put them in an agent prompt, browser field, tool description, or Git. Restart API and worker after changing configuration. Choose only endpoints you operate or trust to receive selected tool arguments. This setting is an operator-controlled network allowlist shared by local workspaces, not production tenant access control. URLs cannot be submitted by a model or browser. HTTPS is required except for explicit loopback HTTP; redirects are rejected and environment HTTP proxies are ignored.

The UI discovers tool definitions dynamically. Adding another compatible server/tool does not require writing another FORGE Python handler. URL/credential entry and OAuth account linking in the frontend are not implemented; this initial flow uses server-side configuration and bearer/no-auth servers.

## Execution and persistence

- Migration `0007_mcp_tools` adds nullable `tools.connection_config`. Existing local tool rows remain valid. The existing database trigger protects this column as immutable along with the rest of the tool revision.
- Connection snapshots contain the server label, endpoint hash, and remote definition, never the credential or raw endpoint URL. Provider-facing names have stable namespaces to avoid collisions.
- Discovery is repeated at registration and compared against the reviewed fingerprint. Every approved execution rediscovers and compares the exact saved definition. Changed schemas/descriptions/annotations or changed endpoints fail visibly; register and bind a new revision instead of altering an existing one.
- Input JSON Schema validation, organization ownership, active status, exact agent binding, call-count and runtime limits apply before execution.
- Before an external call, the ledger commits RUNNING. Completed result/checkpoint evidence follows. If interrupted between these steps, recovery refuses to repeat the unknown call. `/retry` also refuses an already authorized external attempt, even after a timeout or failure. Approval alone cannot guarantee remote idempotency.
- Existing approval expiry, denial, cancellation, and queued continuation apply. Waiting consumes the agent's wall-clock runtime budget. Disabling a revision prevents future authorization; already authorized calls may finish.
- Text/structured results are bounded and validated, then given back to the model through the existing tool exchange. MCP resources/prompts, sampling, elicitation, images, and arbitrary executable uploads are not enabled.

## Dependencies and interoperability limits

Added official `mcp>=1.28,<2` (locked 1.30.0, maintained v1 SDK) and `jsonschema>=4.23,<5` (locked 4.26.0), with transitive versions in `uv.lock`. SDK documentation: https://github.com/modelcontextprotocol/python-sdk/tree/v1.x . The SDK owns initialization, Streamable HTTP sessions, list pagination, and tool calls; FORGE owns authorization and evidence.

This adapter accepts object JSON schemas with no `$ref`, `$dynamicRef`, regex pattern constraints, or recursive references. Schema size/depth, tool count/pages, HTTP response bytes, execution time, and final result size are capped. A catalog containing an unsupported definition fails discovery explicitly. JSON Schema format strings are annotations, not additional format validators. Output content is text plus optional structured JSON; multimedia/resources are rejected. OAuth, stdio process launching, legacy SSE endpoints, externally enforced exactly-once effects, per-tenant credential storage, quotas, and price enforcement remain future work. Production API access remains blocked by the existing development-only guard.

## Files and reading order

| File | Purpose and relationship |
| --- | --- |
| `pyproject.toml`, `uv.lock` | Client/schema dependencies and reproducible resolution. |
| `src/forge/tools/mcp_client.py` | Server configuration, bounded SDK transport, schema/discovery checks, execution and drift detection. Called by registry and Tool Hub. |
| `src/forge/tools/mcp_registry.py` | Reviewed fingerprint → immutable namespaced Tool revision; internal approval policy; binding checks. |
| `src/forge/tools/models.py` | Nullable connection snapshot column. |
| `migrations/versions/0007_mcp_tools.py` | Forward/backward schema change; existing tool immutability trigger also protects the new column. |
| `src/forge/tools/registry.py` | Accepts valid pinned MCP revisions alongside installed local definitions. |
| `src/forge/tools/hub.py` | Input validation → deterministic MCP approval → durable external claim → call/result ledger. |
| `src/forge/approvals/service.py` | Historical inline continuation no longer requires an unrelated refund policy for MCP-only runs. |
| `src/forge/durability/service.py` | Blocks retries after any authorized MCP attempt with potentially unknown effects. |
| `src/forge/api/tools.py` | Thin server listing/discovery/registration routes. |
| `web/lib/api/types.ts`, `web/lib/api/forge.ts` | Dynamic tool names and typed MCP API client. |
| `web/app/api/forge/[...path]/route.ts` | Explicit same-origin proxy allowlist for MCP endpoints. |
| `web/components/tools/mcp-tools.tsx` | Server selection, schema review, registration, disable/enable, next-step guidance. |
| `web/components/tools/tools-screen.tsx` | Integrates MCP into the existing Tool Hub and corrects local-only copy. |
| `web/components/agents/version-form.tsx` | Explains external permissions and excludes internal MCP policy from refund choices. |
| `web/components/approvals/approval-panel.tsx` | Generic tool-call wording, preserving exact-payload review. |
| `examples/mcp_code_server.py` | Independently runnable local MCP code inspection server. |
| `tests/test_mcp.py` | Configuration/schema checks and real HTTP SDK round trip/drift rejection. |
| `tests/test_mcp_postgres.py` | Registration, scope, immutable bindings, input rejection, approval/denial, continuation, retry blocking and interrupted worker recovery. |
| `tests/test_postgres.py` | Migration head expectation updated; downgrade/upgrade and Alembic metadata check retained. |
| `web/tests/mcp-tools.test.tsx` | Empty setup state and fingerprint-preserving frontend registration. |
| `web/tests/e2e/console.spec.ts` | Existing approval labels updated; new real MCP browser workflow and mobile overflow check. |
| `forge.md/05_TOOLS_POLICIES_APPROVALS.md`, `forge.md/08_API_CONTRACT.md` | Accepted current scope and endpoint contracts. |
| `docs/CODE_REVIEW_GUIDE.md`, `docs/MCP_SESSION.md` | Reading order, setup, implementation/report and limitations. |

Read client → registry/model/migration → Hub → approval/retry services → API → frontend → tests. Concrete request: frontend Discover invokes `catalog`; Register rechecks fingerprint and stores the Tool; version creation resolves its exact ID; the model requests its alias; Hub validates and saves approval; reviewer approves; worker rechecks authority, commits the claim, calls MCP, persists output and resumes the model.

User changes in `.env.example` and `src/forge/db/session.py`, and generated `web/AGENTS.md`/`web/CLAUDE.md`, are excluded from this session's commit.

## Local session state

Applied migration 0007 to `forge_local` (additive only), restarted the routed API on port 8000 and worker, and started the example MCP server on port 8040. Frontend remains on port 3000. A read-only browser check in FORGE Development successfully discovered `inspect_code`; no agent version or live run was created for you. Refresh Tools to begin registration.

Created ignored `.tools/mcp-servers.env` with the local `code` endpoint, permissions 0600. Source it alongside your existing provider settings when restarting API/worker. Existing provider/reviewer credentials were preserved. Disposable test API/worker were stopped after tests. These terminal processes are not installed as system services.

## Verification

- `uv run pytest -q` with disposable PostgreSQL/Redis: **149 passed**. After refining SDK exception-group handling, the focused 10-case transport suite also passed.
- Full-suite migration test verifies downgrade to base, upgrade to head, and `alembic check` against a disposable database; never against `forge_local`.
- `uv run ruff check src tests migrations examples` and formatting checks: passed for task files.
- Frontend `npm run test`: 19 passed; `npm run lint`, `npm run typecheck`, `npm run build`: passed.
- Browser suite: nine scenarios passed including real MCP discovery/approval/execution. One existing polling scenario encountered a closed Chromium session; its targeted rerun passed in 3.4 seconds. All 10 scenarios passed across those runs.
- Tests use the fake model backend and isolated database/Redis. No paid model requests were made for verification.

Review questions: Why does a server's read-only hint not authorize calls? What is pinned when registering a tool? What happens after a worker dies during an external call? Why must both API and worker share server configuration? Why does OAuth require additional work beyond entering an API key?
