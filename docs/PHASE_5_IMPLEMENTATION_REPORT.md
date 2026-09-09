# Phase 5 — Policy and approval implementation report

## 1. Implemented functionality

Implemented the user-authorized Phase 5 on `dev`. The branch was clean and synchronized before this session; no GitHub push or commit was performed. Read the working rules, phase plan, tool/policy/approval, schema/API/security, and FORGE-owned runtime decision before editing.

- Installed immutable `demo-refund` 1.0.0 policy with USD thresholds: <=100 ALLOW, >100 through 500 REQUIRE_APPROVAL, >500 DENY.
- HIGH-risk `issue_refund` 1.0.0, with strict positive decimal-string amount and synthetic customer ID. This writes a local `demo_refunds` row; no money, payment API, or external customer system is involved.
- Validate policy ownership/installed revision when creating a version and before running. Refund tool permission requires a policy binding. Earlier unresolved versions are preserved and fail resolution; clone with valid references.
- Save exact organization/run/tool/policy/hash/payload/expiry approval evidence. Approval, private checkpoint, pending tool status, waiting run state, and event commit atomically.
- Local bearer reviewer credential plus server-owned reviewer UUID; no client-supplied identity or model authorization. Production remains blocked. This is one local operator, not organization membership IAM.
- Confirmed approve/deny, immutable first decision, idempotent same-verdict retry, conflict rejection, expiry/denial cancellation, and durable resume-request evidence.
- Explicit resume restores the original run/batch/model response/exchanges and rechecks deadline, binding, policy, active tools, provider/SDK/build/schema compatibility. It claims the run under a PostgreSQL lock so concurrent requests cannot execute twice.
- Multiple approval pauses reuse prior completed calls. Gemini opaque signatures survive private JSON checkpoint serialization. Checkpoint content has no public API endpoint and is excluded from public model-call evidence and repr.
- Console registration, policy selection, approval details, confirmation, reviewer credential/reason entry, reload-safe evidence, and Resume approved run button.

## 2. Files, directories, and caller relationships

New directories: `src/forge/approvals/` owns approval/policy records and services; `web/components/approvals/` owns the run review UI. Existing runtime/tools/API/registry directories retain their responsibilities. No speculative worker/queue directories were created.

### New files

| File | Purpose / caller |
| --- | --- |
| `src/forge/approvals/__init__.py` | Domain package. |
| `src/forge/approvals/models.py` | Policy, Approval, RunCheckpoint, DemoRefund SQLAlchemy records used by Hub/services/Alembic. |
| `src/forge/approvals/policy.py` | Idempotent installed-policy registration, same-org revision resolution, and deterministic Decimal verdict. Called by registry, runtime, and Hub. |
| `src/forge/approvals/service.py` | Decision serialization, terminal cancellation evidence, saved continuation checks and single-executor resume. Called by thin API handlers. |
| `src/forge/api/approvals.py` | Policy/approval routes and typed evidence/body schemas; reviewer credential dependency maps to server UUID. |
| `src/forge/runtime/checkpoints.py` | Private JSON codec for model results/exchanges and opaque provider bytes. Used by engine/service; never a public read endpoint. |
| `migrations/versions/0005_policy_approval.py` | Four tables, tool status extension, immutable policy/checkpoint and approval-binding guards; reversible disposable migration tests. |
| `tests/test_approvals_postgres.py` | 17 real-PostgreSQL cases including amount boundaries, restart, first decision, scope/auth, expiry/disable, immutable evidence, concurrency, changed payload, multiple pauses, and refund rollback. |
| `tests/test_checkpoints.py` | Exact signed provider-content roundtrip through JSON, preserving function-call ID/results. |
| `web/components/approvals/approval-panel.tsx` | Scoped polling, exact request evidence, credential/reason, confirmed decision, explicit resume; token stays in memory and clears on reload/run/workspace switch. |
| `docs/PHASE_5_IMPLEMENTATION_REPORT.md` | This session report. |

### Updated backend, configuration, and tests

| File | Change |
| --- | --- |
| `.env.example` | Documents optional reviewer settings without credentials. |
| `.github/workflows/frontend.yml` | Disposable CI reviewer configuration so browser approval flow runs in CI. |
| `migrations/env.py` | Registers approval-domain metadata. |
| `src/forge/agents/service.py` | Resolves exact policy references during new immutable version creation. |
| `src/forge/core/config.py` | Secret reviewer token (minimum length 32) and reviewer UUID. |
| `src/forge/main.py` | Includes approval/policy routes. |
| `src/forge/model_router/base.py` | Clarifies private persisted continuation versus public evidence. |
| `src/forge/model_router/gemini.py` | Clarifies original signed content is also restored from checkpoints; SDK execution remains manual. |
| `src/forge/runtime/engine.py` | Resume saved batch, skip original model call, pause/checkpoint atomically, reuse earlier results. |
| `src/forge/runtime/service.py` | Accept valid policy bindings, pin limits/policy IDs in execution config, preserve waiting runs instead of marking completed; phase5 build identity. |
| `src/forge/runtime/state.py` | Allows tool wait → approval wait. |
| `src/forge/tools/builtins.py` | Strict refund input/output and idempotent local refund handler. |
| `src/forge/tools/hub.py` | Refund policy, pending approval creation, exact approval verification before handler, reuse without double-counting limits. |
| `src/forge/tools/models.py` | Adds WAITING_FOR_APPROVAL tool-call status. |
| `src/forge/tools/policy.py` | Clarifies existing low/medium demo allowlist role. |
| `src/forge/tools/schemas.py` | Allows installed issue_refund registration. |
| `tests/test_postgres.py` | Expects migration 0005; retains disposable downgrade/upgrade/metadata checks. |
| `tests/test_registry_postgres.py` | Keeps future evaluation staging coverage; arbitrary policy IDs now correctly fail earlier at version creation. |
| `tests/test_runtime_postgres.py` | Removes superseded “all policies unsupported” case; new policy rejection covered in Phase 5 tests. |

### Updated frontend

| File | Change |
| --- | --- |
| `web/app/api/forge/[...path]/route.ts` | Restricted policy/approval/resume route allowlist; forwards Authorization only for decision/resume, retaining origin checks. |
| `web/components/agents/version-form.tsx` | Policy list, exact binding selection, refresh, and clone values. |
| `web/components/layout/app-shell.tsx` | Current Phase 5 scope copy. |
| `web/components/runs/run-detail-screen.tsx` | Poll approval waits and mount per-run approval panel. |
| `web/components/tools/tools-screen.tsx` | Refund tool and installed policy registration. |
| `web/lib/api/forge.ts` | Centralized policy/approval/decision/resume HTTP functions. |
| `web/lib/api/types.ts` | Refund tool name, Policy and Approval evidence types. |
| `web/lib/schemas.ts` | Exact policy UUID array validation. |
| `web/lib/tool-demo.ts` | Explicit fake refund command example. |
| `web/tests/e2e/console.spec.ts` | Full register/bind/pause/approve/reload/resume journey and mobile overflow assertion. |
| `web/tests/forms-and-storage.test.tsx` | Version-form valid fixture includes policy selections. |
| `web/tests/proxy.test.ts` | Credential forwarding restricted to review/resume actions. |

### Updated documentation

`README.md`, `web/README.md`: current scope and browser/credential walkthrough. `docs/CODE_REVIEW_GUIDE.md`: ordered code review and ordinary-function versus model-tool-call map. `forge.md/00_INDEX.md`: report link. `04_RUNTIME_AND_STATE_MACHINE.md`: pause/resume path. `05_TOOLS_POLICIES_APPROVALS.md`: exact current contract and limitations. `07_DATABASE_SCHEMA.md`: actual migration. `08_API_CONTRACT.md`: routes/auth/retries/errors. `11_PHASED_IMPLEMENTATION_PLAN.md`: Phase 5 review checkpoint. `12_ARCHITECTURE_DECISIONS.md`: scoped local reviewer/private continuation/explicit resume choices. `FORGE_FRONTEND_SPEC.md`: implemented console extension. Historical reports are preserved.

## 3. Migration, dependencies, local data

Migration **0005_policy_approval** follows 0004. Adds four tables; does not rewrite prior agent versions or delete existing local workspaces/runs. Policy rules are stored in immutable JSON on the revision rather than a separate editable policy_rules table. Checkpoint schema version is 1. Approval expiry is the earlier of 24 hours or the original runtime deadline. Local refund/result writes share a transaction/savepoint; output failure rolls back the effect.

No package or lockfile dependency was added. Existing SQLAlchemy/Pydantic/Google SDK/frontend packages suffice. `.tools/local-reviewer.env` was generated locally with a random credential and UUID, permission 600, and loaded into the local API. It is ignored and not included in this inventory as tracked source. Never commit it. Generated build caches/screenshots remain ignored.

Local `forge_local` was upgraded and checked without destructive reset. Migration downgrade/upgrade runs only on disposable `forge_test_utf8`. Browser tests create their own uniquely named workspaces. API and frontend were restarted to load this phase and remain available at ports 8000 and 3000, using fake mode.

## 4. Tests and results

Final results are recorded below after verification. Real Gemini network execution is not tested; signed continuation codec and existing manual SDK adapter tests are tested locally. No remote CI run is claimed.

- Python/PostgreSQL: 105 tests pass (includes 17 approval integration cases and signed checkpoint roundtrip).
- Ruff lint/format: pass.
- Alembic disposable upgrade/downgrade/upgrade and local metadata agreement: pass.
- Frontend unit tests: 15 pass.
- TypeScript, ESLint, formatting, production build: pass.
- Playwright: all 6 flows pass, including the real local API approval flow; credential clears on reload and mobile page does not overflow.
- Mobile completed-refund inspector visually inspected.

Two existing Starlette/HTTPX and AnyIO deprecation warnings remain. During development, the generated migration's constraint naming needed `op.f` to avoid double-prefixing; two older tests were updated because policy validation now happens at version creation. Those issues were fixed and checks rerun.

## 5. Commands run

Inspection used `rg`, file reads, Git status/diff, and listener checks. Main commands:

```sh
.tools/bin/uv run ruff check src tests migrations
.tools/bin/uv run ruff format --check src tests migrations
FORGE_TEST_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_test_utf8 .tools/bin/uv run pytest -q
FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_local .tools/bin/uv run alembic upgrade head
FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_local .tools/bin/uv run alembic check
.tools/bin/uv pip install --python .tools/production-venv/bin/python --no-deps --reinstall .
# Local API environment also loads ignored .tools/local-reviewer.env.
FORGE_ENVIRONMENT=local FORGE_MODEL_BACKEND=fake FORGE_DATABASE_URL=postgresql+asyncpg://forge@127.0.0.1:55432/forge_local .tools/production-venv/bin/uvicorn forge.main:create_app --factory --host 127.0.0.1 --port 8000
# In web/, with Homebrew Node 22 on PATH:
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
npm start
```

Autogeneration used Alembic revision `0005`, renamed to `0005_policy_approval` before successful application, then reviewed/extended with guards and the status constraint. No earlier migration was edited.

## 6. Limits and unresolved work

- All refunds are local simulations. No payment provider, real money, external idempotency guarantee, or live Gemini call is claimed.
- Local reviewer credential identifies one configured operator. It is not production membership/login; production API use remains blocked.
- Decisions survive restart and explicit resume restores approval checkpoints. A crash after resume has claimed execution, or during ordinary model/tool execution, can leave an unfinished run; general recovery, queues, Redis, retries, and outbox belong to Phase 6.
- Expiry is enforced and materialized on decision/resume, without a scheduled background sweeper. Waiting counts toward the original deadline; review promptly.
- Approval and resume are deliberately separate HTTP/UI actions. The first saves durable intent; the second executes in process. No queue delivery is implied.
- Checkpoints contain private provider content required for continuation. They have no public endpoint; database access remains privileged. Production encryption/retention/authentication is not completed by this phase.
- Resume fails visibly on disabled tools, invalid policy references, incompatible provider/SDK/build, and changed request binding. It never silently changes provider or permission to complete a request.
- Generic monetary model-cost enforcement, real provider fallback, full dashboard/approvals inbox, and deployment features remain later work.

## 7. Concrete walkthrough and recommended next step

Open http://127.0.0.1:3000/tools. Choose a workspace. Register `issue_refund`, then Register refund policy. Clone an agent version; select both revisions, use a new label, and set runtime to 600 seconds for review time.

Test `/tool issue_refund {"customer_id":"cust_001","amount_usd":"425.00"}`. The run pauses with one recorded model call and one waiting tool call. Inspect the normalized amount/customer/hash/expiry. Open ignored `.tools/local-reviewer.env` locally and copy only the token value into Local reviewer credential. Enter a reason, confirm Approve refund, then Resume approved run. Expect COMPLETED, two model calls, one tool call, and one SIMULATED refund. Change the amount to 50.00 or 700.00 in new runs to see automatic allow or denial.

Follow: browser `api.createRun` → RunService → RuntimeEngine → model request data → ToolHub → refund_decision → pending Approval + RunCheckpoint → browser `api.decideApproval` → reviewer dependency → ApprovalService.decide → `api.resumeRun` → ApprovalService.resume → saved batch → ToolHub exact approval check → execute_builtin local refund → final model answer and evidence.

Review with `docs/CODE_REVIEW_GUIDE.md`. Phase 6 is the next roadmap stage, but was not started. No GitHub action was taken this session.
