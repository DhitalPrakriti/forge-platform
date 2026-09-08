# FORGE frontend local console — implementation and review

## 1. Implemented functionality

Read the full `forge.md/FORGE_FRONTEND_SPEC.md` and the current backend contracts before implementation. The user requested a frontend early because Swagger was confusing. Implemented the supported parts of F1–F3 against the existing Phase 3 backend, and added a current-scope table to the specification. The remaining product screens are future requirements.

The console is available locally at **http://127.0.0.1:3000**. The API remains at **http://127.0.0.1:8000**. The current local API uses **fake** model execution, so testing this flow does not require a provider key.

Implemented:

- Responsive application shell with Overview, Agents, Runs, and Workspace navigation; API readiness; keyboard focus and skip link.
- Create a workspace or connect an existing organization UUID once. Subsequent requests automatically carry the organization header.
- Workspace picker remembering verified records in this browser; organization-scoped query keys and screen reset on switching.
- Overview using backend readiness and the first page of actual agent records. No invented deployment metrics or charts.
- Paginated agent registry, agent identity creation, agent detail, and paginated versions.
- Immutable draft version creation with goal, instructions, model, runtime limits, and saved budget; inspect full configuration; clone into a new version; archive with an accessible confirmation dialog.
- Single-message playground. The backend chooses fake or Gemini; the frontend never asks for provider secrets.
- One idempotency key per run attempt. A lost transport response retains the original request/key for **Retry same request** while the page remains open.
- Run inspector showing actual status, output, sequence-ordered events, provider/model identity, usage, latency, cost, and failure evidence. Active runs poll every two seconds.
- Browser-local recent run IDs per workspace and a form to open an existing run UUID. Details always come from the API.
- Explicit fake labels, unknown-cost display, loading/error/empty states, backend error codes and trace IDs.
- Restricted same-origin Next.js proxy using the current FastAPI endpoints. Provider calls, database access, and business rules remain on the backend.
- Frontend unit/browser tests, formatting/lint/type/build scripts, and a GitHub Actions frontend workflow.

The first browser run caught an origin-check bug: Next's internal URL used `localhost` while the browser used `127.0.0.1`. The proxy now compares against the browser Host, and a regression test covers this case. Cross-origin mutations are still rejected.

## 2. Every file and directory in this session

All paths below are relative to the repository root. Earlier uncommitted Phase 3 and runtime-reversal changes were preserved; they are not frontend changes.

### Existing project files updated

| File | Change and reason |
| --- | --- |
| `.gitignore` | Excludes Node packages, Next build output, coverage, browser artifacts, and TypeScript build cache. |
| `.dockerignore` | Excludes `web` from the existing backend-only Docker build context. |
| `README.md` | Adds the console URL, startup commands, workflow, and review links. |
| `forge.md/00_INDEX.md` | Links the frontend specification and this report. |
| `forge.md/FORGE_FRONTEND_SPEC.md` | Preserves the user-provided full blueprint; adds implemented-scope rules and current API limitations at the top. |
| `docs/CODE_REVIEW_GUIDE.md` | Adds frontend reading order, caller/callee walkthrough, and review questions. |

### New project documentation and automation

| File | Responsibility |
| --- | --- |
| `docs/FRONTEND_LOCAL_CONSOLE_SESSION.md` | This session's complete report. |
| `.github/workflows/frontend.yml` | Node/Python setup, isolated PostgreSQL, fake API, frontend checks, browser tests, and failure artifacts. No provider key is needed. |

### `web/`: application and tooling

| File | Responsibility |
| --- | --- |
| `web/README.md` | Startup, first fake run, limitations, test commands, and references. |
| `web/package.json` | Runtime/test dependencies and npm scripts. |
| `web/package-lock.json` | Generated dependency lock for reproducible `npm ci`. |
| `web/.nvmrc` | Selects Node 22 for version managers. |
| `web/.env.example` | Documents server-only backend address; contains no provider key. |
| `web/.prettierignore` | Excludes generated/vendor files from formatting. |
| `web/tsconfig.json` | Strict TypeScript, Next plugin, and `@/` source alias. |
| `web/next-env.d.ts` | Generated Next type references. |
| `web/postcss.config.mjs` | Enables Tailwind's PostCSS integration. |
| `web/eslint.config.mjs` | Next/TypeScript lint rules and generated-file exclusions. |
| `web/components.json` | shadcn manual setup metadata and aliases for locally owned UI primitives. |
| `web/vitest.config.ts` | DOM unit-test environment, setup file, and alias resolution. |
| `web/playwright.config.ts` | Chromium integration tests using a production frontend on port 3100. |

### `web/app/`: thin route entry points

| File | Calls / responsibility |
| --- | --- |
| `web/app/layout.tsx` | Wraps pages in Providers and AppShell; supplies metadata and global CSS. |
| `web/app/globals.css` | Shared visual tokens, layout, typography, forms, status colors, tables, dialogs, responsive rules, and reduced motion. |
| `web/app/page.tsx` | Renders OverviewScreen. |
| `web/app/workspace/page.tsx` | Renders WorkspaceScreen. |
| `web/app/agents/page.tsx` | Renders AgentsScreen. |
| `web/app/agents/new/page.tsx` | Renders CreateAgentScreen. |
| `web/app/agents/[agentId]/page.tsx` | Resolves route ID and renders AgentDetailScreen. |
| `web/app/agents/[agentId]/versions/new/page.tsx` | Resolves agent ID and optional clone source; renders CreateVersionScreen. |
| `web/app/agents/[agentId]/versions/[versionId]/page.tsx` | Resolves IDs and renders VersionDetailScreen. |
| `web/app/agents/[agentId]/versions/[versionId]/playground/page.tsx` | Resolves IDs and renders PlaygroundScreen. |
| `web/app/runs/page.tsx` | Renders RunsScreen. |
| `web/app/runs/[runId]/page.tsx` | Resolves run ID and renders RunDetailScreen. |
| `web/app/api/forge/[...path]/route.ts` | Restricts allowed paths/methods, checks mutation origin, forwards organization/idempotency headers to the fixed backend, preserves errors/trace IDs, and sanitizes connection failures. |
| `web/app/error.tsx` | Recoverable page-level error fallback. |
| `web/app/not-found.tsx` | Unknown-page fallback with an overview link. |

### `web/components/`: screens and reusable presentation

| File | Responsibility and calls |
| --- | --- |
| `web/components/layout/providers.tsx` | Owns QueryClient and browser workspace context; reads/writes storage through `lib/storage.ts`. |
| `web/components/layout/app-shell.tsx` | Navigation, workspace picker, health query, footer, and hydration gate; remounts screen state when organization changes. |
| `web/components/workspace/workspace-screen.tsx` | Validated create/connect forms → `api.createOrganization` / `api.organization` → workspace context. |
| `web/components/overview/overview-screen.tsx` | Actual readiness and first-page agents; explains the supported testing workflow. |
| `web/components/agents/agent-screens.tsx` | Agent list/create/detail and version list; query pagination, create mutation, navigation. |
| `web/components/agents/version-form.tsx` | Converts validated form values to VersionInput; new draft or clone with preserved source bindings. |
| `web/components/agents/version-screens.tsx` | Loads agent/source/version, renders immutable configuration, controls archive confirmation and cache invalidation. |
| `web/components/runs/playground-screen.tsx` | Message form, retained request/idempotency key, create-run mutation, uncertain retry, navigation to inspector. |
| `web/components/runs/runs-screen.tsx` | Opens UUIDs and loads browser-local recent IDs through organization-scoped run queries. |
| `web/components/runs/run-detail-screen.tsx` | Run/event/model-call queries, active polling, terminal refresh, output/errors, usage, costs, raw records, and copy ID. |
| `web/components/ui/button.tsx` | Locally owned shadcn-style Button using Radix Slot and class variants; supports links without nested interactive elements. |
| `web/components/ui/confirm-dialog.tsx` | Radix AlertDialog for archive; focus management, labels, cancel, and pending action. |
| `web/components/ui/shared.tsx` | Badge, Card, PageHeading, Loading, Empty, ErrorNotice, Field, JsonDetails, and Pagination. Field links controls to validation/help text. |

### `web/lib/`: contracts, transport, and small helpers

| File | Responsibility |
| --- | --- |
| `web/lib/api/types.ts` | TypeScript interfaces corresponding to the existing backend read/write schemas. |
| `web/lib/api/client.ts` | Shared fetch function, organization header, no-store requests, and ApiError normalization. |
| `web/lib/api/forge.ts` | Named, typed functions for supported organization/agent/version/run/health endpoints. |
| `web/lib/schemas.ts` | Zod form validation for identity, UUIDs, version fields, and run input. Backend remains authoritative. |
| `web/lib/storage.ts` | Validated localStorage for workspace records/selection and up to 50 run IDs per organization; handles corrupt or unavailable storage. No prompt/output persistence. |
| `web/lib/utils.ts` | Class composition, timestamps, short IDs, and null-aware monetary formatting. |

### `web/tests/`: behavior verification

| File | Responsibility |
| --- | --- |
| `web/tests/setup.ts` | DOM matchers, cleanup, stub reset, and storage isolation per test. |
| `web/tests/client.test.ts` | Organization/header contracts, preserved retry keys, trace errors, sanitized non-JSON responses. |
| `web/tests/forms-and-storage.test.tsx` | Actual invalid form behavior, UUID/config boundaries, scoped/corrupt storage, and null versus zero cost. |
| `web/tests/proxy.test.ts` | Loopback Host/origin handling, scoped header forwarding, cookie exclusion, blocked origin/path, sanitized upstream failure. |
| `web/tests/e2e/console.spec.ts` | Real-API create/version/run/clone/archive/scope/retry flow, validation/duplicate errors, responsive screenshots; an isolated fixture checks polling to failure and unknown cost. |

Generated, ignored artifacts include `web/node_modules/`, `web/.next/`, `web/test-results/`, and `web/tsconfig.tsbuildinfo`. These are not project source to review line by line. Chromium was downloaded to the local Playwright browser cache. Node 22 and its Homebrew dependencies were installed locally; shell startup files were not changed.

## 3. Migrations and backend changes

**No migration added. No backend source or API contract changed.** Used the existing organization, registry, health, run, event, and model-call endpoints. PostgreSQL schema remains at `0003_initial_runtime` from the previous session.

The backend integration suite used the disposable `forge_test_utf8` database. Browser tests used unique `ui-e2e-…` organizations in the already-running local backend; they did not drop tables, reset `forge_local`, or modify existing user agents. Test records remain in the database for inspection.

## 4. Dependencies and why they exist

The implementation follows the stack requested in the frontend document:

- **Next.js 16 / React 19 / TypeScript:** routing, rendering, strict types, and a small server-side API bridge.
- **Tailwind / PostCSS:** styling integration with shared CSS tokens and responsive components.
- **Radix Slot and AlertDialog, class-variance-authority, clsx, tailwind-merge:** locally owned shadcn-style button/dialog primitives and class composition.
- **TanStack Query:** server-state fetching, scoped caches, mutations, invalidation, and polling.
- **React Hook Form / Zod / resolver adapter:** form state, client validation, and inline errors.
- **Lucide:** consistent functional UI icons.
- **Vitest, Testing Library, jsdom:** component and transport tests.
- **Playwright:** actual browser/API integration, desktop/mobile checks, and screenshots.
- **ESLint / Prettier / type packages:** reviewable formatting, lint, and type checks.

No chart package, global state library, LangChain/LangGraph dependency, graph database, or frontend provider SDK was added. The lockfile records exact resolved dependency versions. The dependency installation reported no known vulnerabilities at installation time.

Technical references consulted: [Next.js installation](https://nextjs.org/docs/app/getting-started/installation), [shadcn manual installation](https://ui.shadcn.com/docs/installation/manual), [TanStack Query React documentation](https://tanstack.com/query/latest/docs/framework/react).

## 5. Commands run

Read-only inspection included `rg`, file reads, `git status`, and health requests. Installation and verification commands, with Node's Homebrew bin directory on PATH:

```sh
brew install node@22
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
# From web/: dependencies listed in package.json were installed with npm install;
# this generated package-lock.json. Future installs use npm ci.
npx playwright install chromium
npm run format
npm run typecheck
npm run lint
npm test
npm run build
npm run test:e2e
npm start
```

Backend regression command, from the repository root:

```sh
FORGE_TEST_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_test_utf8 .tools/bin/uv run pytest -q
```

The first TypeScript/lint pass found a JSX delimiter typo, which was fixed before browser tests. One npm check was initially invoked from the repository root instead of `web/`; it made no project change and was rerun from the correct directory. Initial browser tests exposed the loopback-origin bug described above; all were rerun after correction. Formatting was applied to all new frontend source.

## 6. Results

| Check | Result |
| --- | --- |
| TypeScript | Passed |
| Prettier formatting | Passed |
| ESLint | Passed |
| Production Next.js build | Passed |
| Vitest / Testing Library | 14 tests passed |
| Playwright / Chromium | 4 tests passed |
| Existing Python/PostgreSQL suite | 68 tests passed |
| Desktop/mobile inspection | Overview and run inspector checked; mobile test verified no page-wide horizontal overflow at 390px |
| Duplicate-run retry | Lost the first response after backend acceptance; retry used the same key and returned the same persisted run ID |
| Organization isolation | Other workspace showed no recent runs/agents; opening the original run returned scoped 404 |
| Live console startup | Port 3000 returned HTTP 200; its proxied API readiness returned `ready` |

The typecheck script generates Next route types before running TypeScript so it also works on a fresh checkout without an existing `.next` directory. Final tracked-file whitespace checks passed.

Two pre-existing Python dependency deprecation warnings remain (Starlette/HTTPX and AnyIO). Playwright emitted a terminal color environment warning, not a test failure. The new GitHub Actions workflow is configured but has not run remotely; this session did not commit, push, or open a PR.

## 7. Limits and unresolved work

- This is the supported local testing slice, not the completed production frontend. Production login/membership, server-side organization and run listing, advanced search, edit UI, tooling, staging, evaluations, deployment, and observability dashboards remain later work.
- The running backend is fake. No real Gemini request was verified during this frontend session.
- Run creation is synchronous. The inspector cannot show a live event stream before the backend returns the run ID. Active saved runs poll; there is no SSE.
- The Phase 3 backend cannot recover a run left RUNNING by a process failure. The console can display that state but cannot repair it.
- Retry input/key lives in page memory. Keep the page open after uncertain errors. Navigating or reloading loses that context; a run may already exist in PostgreSQL.
- Browser history is not an organization-wide run index. Local storage contains workspace context and IDs, not authentication credentials or model prompts/outputs.
- Budget values are stored configuration only; enforcement and real price calculation remain deferred.
- The clone form preserves source bindings but does not provide editors for future tools/policies/fallback/evaluation dependencies. The backend still validates whether the resulting version can run.
- Browser checks cover Chromium desktop and a narrow mobile viewport, not a full Safari/Firefox or accessibility certification.

## 8. Recommended next step and walkthrough

Review and try the local console before beginning another backend phase:

1. Open **http://127.0.0.1:3000**.
2. Create a workspace or connect an existing organization UUID.
3. Create an agent, then a version with model identifier `local-test-model` while the backend is fake.
4. Select **Test version**, send a message, and inspect the saved record.
5. Read `docs/CODE_REVIEW_GUIDE.md` alongside the screen you are using.

Follow one request:

```text
Click Run agent
  → PlaygroundScreen's validated submit callback
  → crypto.randomUUID(): one idempotency key for this attempt
  → api.createRun(org, input, key)
  → request(): automatic X-Organization-ID + Idempotency-Key
  → Next POST /api/forge/runs
  → FastAPI POST /api/v1/runs
  → existing RunService.execute()
  → fake adapter now, or configured Gemini adapter later
  → PostgreSQL run + events + model-call evidence
  → response and navigation to /runs/{id}
  → RunDetailScreen reads persisted run/events/model-calls
```

These are ordinary TypeScript and Python function calls around an HTTP/model request. They are not model-requested business tool calls. The current inspector should show **one model call and zero tool calls**. Tool Hub and policy-controlled function execution remain the next backend work after review.
