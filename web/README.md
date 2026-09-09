# FORGE local console

This Next.js app provides a simpler way to test the existing FORGE backend than Swagger. The implemented slice is workspace setup → agent → immutable version → message → model/tool run → inspector. It is a local development interface, not a production authentication system.

## Run locally

Requirements: Node.js 22+, npm, the migrated FORGE API on port 8000, and PostgreSQL. On the development Mac, `brew install node@22` installed Node. If necessary:

```sh
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
```

From this directory:

```sh
npm ci
npm run dev
```

Open **http://127.0.0.1:3000**. The app binds to loopback. For an optimized build, use `npm run build` followed by `npm start` instead of the development server. Only run one server on port 3000.

The backend defaults to `http://127.0.0.1:8000`. To change it, copy `.env.example` to `.env.local`, set the server-only `FORGE_API_URL`, and restart Next.js. Never put provider keys in this app. The backend owns its model configuration.

## First test without an API key

Start the API with `FORGE_MODEL_BACKEND=fake`, following the root README's database/migration instructions. On the already configured development Mac, run this from the repository root:

```sh
FORGE_ENVIRONMENT=local FORGE_MODEL_BACKEND=fake FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_local .tools/bin/uv run uvicorn forge.main:create_app --factory --host 127.0.0.1 --port 8000
```

Do not start a second API if port 8000 already serves the current backend.

1. Create a workspace with a name and unique lowercase slug. Alternatively, paste an existing organization UUID into **Connect an existing workspace**.
2. Click **Create agent** and enter a name and slug. Saving creates the agent immediately.
3. Add version `v1`, a goal, instructions, and model identifier `local-test-model` for the fake backend. Keep the example limits.
4. Click **Save immutable version**, then **Test version**.
5. Enter a message and press **Run agent**. The inspector should show **COMPLETED**, **FAKE MODEL**, three events, one model call, and zero tool calls.
6. Use **Clone version** to change configuration. The original is immutable. Archive requires confirmation and prevents new runs.

For a real Gemini run, the model identifier must be supported by the configured provider, and the API needs its provider key. This frontend does not validate the provider's model catalog. Saved dollar budgets are not enforced yet.

## What the interface is showing

- Workspace choices are verified organization records remembered in this browser. The API has no organization-list endpoint.
- Agent and version lists are paginated at 20 records per page.
- Runs history stores only the last 50 opened run IDs per workspace in this browser. It is not all runs in the organization. Input/output stays on the backend and in transient page/query state.
- Run creation waits for execution; the inspector opens after the API returns an ID. Active records then poll every two seconds. This is not SSE streaming.
- After a transport failure, keep the playground open and use **Retry same request**. It reuses the original input and key. Reloading or leaving the page loses that retry context; the backend may still contain the run.
- A saved run can be `FAILED` even when creation returned HTTP 201. The inspector uses the run status and error code.
- “Not available” cost means unknown, not free. Fake output and simulated usage are explicitly labelled.
- Local demo tools are available through Tool Hub. Business policies, approvals, staging, evaluations, deployment, cancellation, and replay remain later work.

## Verification

```sh
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Browser tests start the production frontend on **3100** and require the migrated backend on **8000**, configured with **fake** execution. They create uniquely named `ui-e2e-…` organizations and never delete existing data. The CI workflow supplies a separate PostgreSQL database. Local test records remain available for inspection.

Vitest covers form validation, organization headers, structured errors, retry keys, storage isolation, cost display, and proxy behavior. Playwright covers the complete real-API journey and failure/retry behavior. Screenshots and failure traces are generated in ignored `test-results/`.

## Review order

Read `lib/api/types.ts` → `lib/schemas.ts` → `lib/api/client.ts` → `lib/api/forge.ts` → `app/api/forge/[...path]/route.ts` → `components/layout/providers.tsx` → the screen you want to inspect. Route files under `app/` are thin entry points. Domain screens own forms and query orchestration; the backend still owns business rules.

The full file inventory and one function-by-function walkthrough are in [the session report](../docs/FRONTEND_LOCAL_CONSOLE_SESSION.md).

Technical references used: [Next.js installation](https://nextjs.org/docs/app/getting-started/installation), [shadcn manual setup](https://ui.shadcn.com/docs/installation/manual), and [TanStack Query React documentation](https://tanstack.com/query/latest/docs/framework/react).

## Phase 4: test a tool call

1. Open **Tools** in your selected workspace. Register `lookup_customer`, `lookup_transactions`, and/or `create_ticket`.
2. Clone an existing agent version, enter a new version label, and check the needed tools under **Tool permissions**. Keep maximum steps at 12 (a tool request plus a final answer needs at least two model turns).
3. Save the new version and click **Test version**.
4. Expand **Fake-backend tool examples**. Choose **Customer lookup**, **Transactions lookup**, or **Create demo ticket**, then press **Run agent**. These examples fill explicit `/tool` commands and do not change the configured backend provider.
5. Inspect **Tool calls**: exact revision ID, normalized arguments, result/error, ALLOW/DENY, latency, and stable idempotency record. A successful one-tool fake example shows two model calls and one tool call.

The sample customers are `cust_001` and `cust_002`. Customer/transaction data is synthetic. Demo tickets are saved in your organization's local database without contacting an external service. The original agent version keeps its original tool permissions. An unbound tool is denied; an inactive tool cannot newly execute. Disabling requires confirmation and can later be reversed with Enable.

The original Phase 4 milestone added tool polling. Current Phase 6 additionally polls queue/retry/approval waits and supports approvals and local-effect recovery. Monetary budgets and external integrations remain deferred. The Phase 4 changes and complete test results are in [the implementation report](../docs/PHASE_4_IMPLEMENTATION_REPORT.md).

## Phase 5 approval walkthrough

1. In Tools, register `issue_refund` and the refund policy.
2. Clone an agent version, select the refund tool and policy, and save. Use a 600-second runtime limit to allow review time.
3. Test `/tool issue_refund {"customer_id":"cust_001","amount_usd":"425.00"}`.
4. In the run inspector, check the exact amount/customer/hash and expiry. Enter your configured local reviewer credential and reason; confirm Approve refund or Deny refund.
5. For new Phase 6 runs, approval saves the decision and schedules worker continuation automatically. Legacy Phase 5 runs still show Resume approved run. Reloading clears the credential while preserving database evidence.

USD 50.00 allows; USD 700.00 denies. All refunds are simulated local database records. No provider key is needed for fake mode. The session's generated local credential is in ignored `.tools/local-reviewer.env` at the repository root; only its token value belongs in the password field. Production login is not implemented.

The new browser approval test requires `FORGE_APPROVAL_REVIEWER_TOKEN` matching the API. CI uses a disposable test credential; local test runs without this variable explicitly skip that one flow.

## Phase 6 worker controls

Start PostgreSQL, Redis, the migrated API, and `python -m forge.durability.worker` before testing. API and worker must share configuration. New run responses are 202/QUEUED; the run inspector polls worker progress. Cancel run asks for confirmation and displays the saved result after the next safe boundary. A completed effect is not undone. Retry as new run links the new execution to its failed/timed-out original; the server blocks repetition of successful or unknown side effects.

The browser suite now tests queued completion, automatic approval continuation, linked retry, and cancellation controls. The cancellation presentation fixture is isolated from the real worker cancellation tests in the backend suite. See [the Phase 6 implementation report](../docs/PHASE_6_IMPLEMENTATION_REPORT.md).
