# Phase 7 — model fallback, availability, and costs

Implemented 2026-09-18 on `dev`, following the user's choice to finish model reliability and cost tracking before business-service connection work.

## Behavior

- New runs validate all configured primary/fallback models and credentials before admission, then snapshot provider identities, Gemini SDK revision, prices, and the version's budget.
- Queued execution retries transient failures using existing bounded backoff. When attempts are exhausted (or a circuit is open), the worker saves an ordered fallback selection, event, checkpoint, and outbox wakeup. A new worker restores that selection. Exhausting the list terminates the run.
- Fallback is limited to before the first successful response. Authentication, rejected requests, malformed/incomplete/safety responses do not trigger it. Once a model requests a tool, the same provider continues the conversation: native Gemini/OpenAI state is not portable. No tool permissions or approvals are relaxed.
- Passive health is organization/provider/model scoped. Three consecutive transient failures open a 30-second circuit. One half-open probe gets a timeout-based lease after cooldown. Generation checks prevent late responses overwriting a newer circuit state. Health uses actual attempts; no paid monitoring probes are scheduled.
- Costs use the exact reported actual model and the admission-time price snapshot. OpenAI cached input is discounted and reasoning is already included in output usage. Gemini cached input is discounted and reported thinking tokens are added to candidate output. Unsupported or unknown usage/rates remain unknown. Skipped requests and fake calls have zero external model cost.
- Every attempt saves cost details. A run with any unknown charge retains a null total and reports its known subtotal separately. Historic completed runs are not repriced.
- An observed-cost stop prevents further model/tool actions after the known estimate reaches the version budget. The run reports `BUDGET_EXCEEDED`. This is **not a billing cap**: one call may overshoot; failed calls may have charges with no returned usage. It does not bound account-wide spending.
- Frontend: editable ordered fallback models on new/cloned versions; passive model availability on Overview; fallback selection and known/unknown cost evidence on the run inspector.

## Files and directories changed

| File | Responsibility and relationships |
| --- | --- |
| `src/forge/core/config.py` | Server-only `FORGE_MODEL_PRICES` override setting consumed at run admission. |
| `src/forge/runtime/service.py` | Validates candidates, snapshots routing/pricing/budget into each run. |
| `src/forge/durability/engine.py` | Resolves checkpoint candidate, bounded fallback, model binding validation, unknown-outcome accounting, budget checks before actions. |
| `src/forge/runtime/engine.py` | Shared circuit admission → adapter attempt → health observation → pricing, used by durable and inline paths. |
| `src/forge/runtime/models.py` | Nullable per-attempt `cost_details` persistence. |
| `src/forge/runtime/schemas.py` | Exposes saved cost evidence in model-call responses. |
| `src/forge/model_router/models.py` | New `ModelHealth` database mapping. |
| `src/forge/model_router/health.py` | Row-locked breaker transitions, generation fencing, leased recovery probes and scoped listing. |
| `src/forge/model_router/schemas.py` | Explicit public health response fields, excluding internal generation state. |
| `src/forge/model_router/pricing.py` | Validated rate catalog, immutable snapshot/fingerprint, Decimal arithmetic, aggregate costs and budget predicate. |
| `src/forge/model_router/openai.py` | Requests standard service tier and records returned tier; nonstandard tiers cannot silently use standard estimates. |
| `src/forge/api/runs.py` | Thin organization-scoped development `GET /api/v1/models/health`. |
| `migrations/env.py` | Registers new metadata for Alembic checking. |
| `migrations/versions/0008_model_routing.py` | Adds `model_health` and nullable `model_calls.cost_details`; preserves existing data. |
| `tests/test_postgres.py` | Upgrade/downgrade/re-upgrade/schema-check expectations at new head. |
| `tests/test_model_pricing.py` | Exact cached/thinking calculations, missing/invalid/unsupported usage, unknown prices, snapshot independence. |
| `tests/test_model_routing_postgres.py` | Fresh-worker fallback, permanent errors, blocked response, list exhaustion, tool boundary, pinned pricing, budget stop, breaker/probe/generation/scope and skipped requests. |
| `web/lib/schemas.ts` | Bounds and validates fallback text entry. |
| `web/lib/api/types.ts` | Typed health, cost summary, active candidate and cost evidence. |
| `web/lib/api/forge.ts` | Scoped health client method. |
| `web/app/api/forge/[...path]/route.ts` | Allows only the new health GET path through the existing proxy. |
| `web/components/agents/version-form.tsx` | Ordered fallback textarea, immutable clone preservation, accurate budget explanation. |
| `web/components/models/model-health.tsx` | New passive health panel with unknown/open/probing explanations and refresh. |
| `web/components/layout/app-shell.tsx` | Updates the visible backend milestone to Phase 7. |
| `web/components/overview/overview-screen.tsx` | Embeds the health panel for the selected workspace. |
| `web/components/runs/run-detail-screen.tsx` | Known subtotal/unknown total, fallback selection and per-attempt estimate status. |
| `web/tests/model-routing.test.tsx` | Unknown availability, open circuit presentation, fallback validation. |
| `web/tests/e2e/console.spec.ts` | Browser test for saving/cloning fallback order; fixes a pre-existing hard-coded backend URL to respect test isolation. |
| `README.md` | Current behavior, setup, price override example and billing limitations. |
| `docs/CODE_REVIEW_GUIDE.md` | Reading order, request walkthrough and review questions. |
| `forge.md/04_RUNTIME_AND_STATE_MACHINE.md` | Records implemented routing/accounting boundaries alongside historic milestones. |
| `forge.md/09_OBSERVABILITY_RELIABILITY_SECURITY.md` | Records passive health/accounting scope and remaining observability work. |
| `forge.md/11_PHASED_IMPLEMENTATION_PLAN.md` | Phase 7 status and explicit scope limits. |
| `docs/PHASE_7_IMPLEMENTATION_REPORT.md` | This review record. |

Directories expanded: `src/forge/model_router`, `web/components/models`, migration/test/docs directories. No general workflow framework or new package dependency was added. LangGraph remains absent.

Unrelated pre-existing changes to `.env.example`, `src/forge/db/session.py`, and generated `web/AGENTS.md`/`web/CLAUDE.md` were preserved and excluded from the session commit. Credentials remain in ignored local files and were not printed or committed. Test screenshots/traces/build artifacts remain generated, not tracked.

## Pricing basis

Verified standard paid text rates (USD per million tokens):

| Exact model | Input | Cached input | Output |
| --- | ---: | ---: | ---: |
| `gpt-4.1-mini` / `gpt-4.1-mini-2025-04-14` | 0.40 | 0.10 | 1.60 |
| `gemini-3.1-flash-lite` | 0.25 | 0.025 | 1.50 |

Sources: [OpenAI model pricing](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [Gemini thinking usage](https://ai.google.dev/gemini-api/docs/generate-content/thinking), [OpenAI Responses reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create). Catalog revision `standard-text-2026-09-18`, with content fingerprint and exact stored rates. Custom exact-model rates can be supplied with `FORGE_MODEL_PRICES`; configuration errors prevent new run admission rather than guessing.

These are estimates, not invoices. Free-tier credits, discounts, taxes, nonstandard service tiers, multimodal usage, cache-write charges, external tool-service charges and account-wide caps are not implemented. Unknown actual model IDs are not matched by a speculative prefix. No model-provider charges were incurred by this session's tests.

## Verification and commands

- `FORGE_TEST_DATABASE_URL=.../forge_test_utf8 FORGE_TEST_REDIS_URL=.../1 .tools/bin/uv run pytest -q`: **169 passed**. Two existing Starlette/httpx/AnyIO deprecation warnings.
- `.tools/bin/uv run ruff check src tests migrations`: passed.
- Ruff format check over changed backend modules, migrations and new tests: passed. Unrelated user-edited database session file was not reformatted.
- `npm run typecheck`, `npm run lint`, `npm test`, `npm run build` (Node 22): passed, **22 unit tests**.
- Playwright runs against separate fake backend port 8001 and disposable test database/Redis DB 1, never live model credentials. Browser evidence covers existing tools, MCP approval, follow-ups, desktop/mobile widths and new fallback cloning. Initial run: 10 passed; one existing test used port 8000. Corrected it to use `FORGE_API_URL` and reran the affected workflow plus new fallback workflow: **2 passed**. All 11 browser scenarios passed across the initial and targeted rerun. Mobile Overview screenshot was visually inspected.
- Local `alembic upgrade head`: applied `0008_model_routing`; `alembic current` confirms head. API and routed worker restarted with existing private provider/MCP configuration.
- Local API readiness returns `{"status":"ready"}`; scoped model-health endpoint returns an empty list until new provider attempts are observed. An empty list is not a provider-health guarantee.

## Review and manual use

Read admission service → durable fallback cursor → shared model attempt → health → pricing → migration/tests → frontend. A concrete failure path is in `CODE_REVIEW_GUIDE.md`.

Open localhost:3000, choose your workspace, clone an agent version, set primary `gemini-3.1-flash-lite` and optional fallback `gpt-4.1-mini`, then save. Run a short code-review prompt. Inspect actual model, cost evidence and events. A healthy primary should not invoke the fallback. Model availability updates after new real attempts; old runs retain their original records. All fallback provider credentials must be configured even if the primary is healthy.

Inline execution does not support ordered fallback. Queued execution does not switch provider after a successful response or tool request. Unknown-cost failures may make the total unavailable even when fallback succeeds. The configured budget is a stop based on recorded estimates, not a guarantee of staying under a provider charge limit. Production authentication and account-wide billing controls remain future work.

Next recommended phase is Phase 8 observability, after reviewing this change. Business-service connections remain separately planned; they were not silently implemented in this session.
