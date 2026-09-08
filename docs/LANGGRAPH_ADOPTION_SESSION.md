# LangChain/LangGraph adoption session

> **SUPERSEDED 2026-09-06:** The user reversed this adoption. This document is historical, not implementation instructions. Current design: [FORGE runtime decision](../forge.md/14_FORGE_RUNTIME_DECISION.md).

## 1. Functionality / scope

Documentation-only architecture change authorized by the user. Adopt LangChain `create_agent` on LangGraph, official model/tool integrations, framework checkpoints, and interrupt/resume. FORGE retains its deterministic platform services. Establish a persistent code-review process for each session. Current application functionality remains Phase 1; framework packages will be installed when implementing Phase 3 and subsequent phases.

## 2. Every file changed and reading order

Read the new runtime guide first, then the working rules and review guide. Check the affected original specs afterward.

| File | Change |
| --- | --- |
| `forge.md/13_LANGCHAIN_LANGGRAPH_RUNTIME.md` (new) | Default standard agent loop, ownership table, request flow, PostgreSQL consistency, approval/retry rules, phased dependencies, acceptance checks, official sources |
| `forge.md/10_CODEX_WORKING_RULES.md` | Framework-first implementation rules, revised runtime/tool/durability prompts, mandatory session review handoff |
| `docs/CODE_REVIEW_GUIDE.md` (new) | Current directories/files, reading order, review questions, concrete readiness walkthrough, future runtime distinction |
| `forge.md/00_INDEX.md` | Spec version 0.3, canonical framework rule, links to guides |
| `forge.md/01_PRODUCT_VISION.md` | Name the framework underpinning the runtime |
| `forge.md/02_SYSTEM_ARCHITECTURE.md` | LangGraph engine, LangChain integrations, ownership boundaries; remove separate planned workflows module |
| `forge.md/03_AGENT_DEFINITION_AND_REGISTRY.md` | Managed framework runtime and pinned runtime template/build metadata |
| `forge.md/04_RUNTIME_AND_STATE_MACHINE.md` | Separate public run status from graph scheduling; framework checkpoint/retry/interrupt rules |
| `forge.md/05_TOOLS_POLICIES_APPROVALS.md` | Guarded LangChain tool invocation and authenticated LangGraph approval resume |
| `forge.md/07_DATABASE_SCHEMA.md` | Remove proposed custom graph-state table; use official PostgreSQL checkpointer tables and planned thread/build references |
| `forge.md/11_PHASED_IMPLEMENTATION_PLAN.md` | Framework introduction in Phase 3, PostgreSQL approval checkpointing in Phase 5, distributed recovery in Phase 6; session review cadence |
| `forge.md/12_ARCHITECTURE_DECISIONS.md` | Accepted framework choice; replace combined checkpoint/domain transaction claim with separate commits plus reconciliation |
| `README.md` | Runtime direction and review guide links |
| `docs/LANGGRAPH_ADOPTION_SESSION.md` (new) | This session record |

Changed directories: `forge.md/`, `docs/`, and repository root (`README.md`). No source, tests, package lock, CI, or migration files changed. The prior Phase 1 report remains a historical record.

## 3. Dependencies and migration

None added this session. The runtime guide explains planned packages and their owning phases. The PostgreSQL checkpointer's supported driver/pool is separate from existing SQLAlchemy/asyncpg infrastructure. Its own setup/upgrades will run separately from FORGE Alembic migrations.

## 4. Tests

No tests added for the documentation changes. Ran existing tests as a foundation regression check.

## 5. Commands and research

- Read runtime, working rules, decisions, schema, phase plan, and `src/forge/main.py` with `cat`.
- Used `rg -n` to locate runtime/checkpoint/provider references and check for obsolete architecture language.
- Consulted official LangChain agents/integrations and LangGraph overview/persistence/interrupt documentation. Links appear in the runtime guide.
- Used `/tmp/forge_langgraph_docs.py`, targeted Python replacements, and shell heredocs to update the documents. A replacement assertion caught a checkpoint-heading mismatch; corrected the heading and applied the remaining changes, then checked the resulting specs.
- `.tools/bin/uv run ruff check .`
- `.tools/bin/uv run ruff format --check .`
- `.tools/bin/uv run pytest -q`
- Checked local Markdown link targets and balanced code fences after the final documentation edits.

## 6. Results

Ruff lint and formatting passed. Existing tests: 11 passed, 1 integration test skipped because `FORGE_TEST_DATABASE_URL` was unset, with the same two upstream test-library deprecation warnings. No PostgreSQL, Docker, remote CI, model-provider, or LangGraph integration execution was performed this session. The framework is selected and specified, not yet implemented.

## 7. Review questions / remaining implementation work

- Can you explain the difference between FORGE public run status and LangGraph execution state?
- Can you identify where a tool call is authorized before execution?
- Why does an interrupted node need idempotent writes when it resumes?
- Why are two writes to the same PostgreSQL server not automatically a single transaction?
- Can you trace the current readiness request using the review guide?

Checkpoint/domain crash recovery and middleware enforcement must be proven in their implementation phases. Framework API/package compatibility must be verified again when dependencies are added. Existing Docker/hosted CI verification limits remain unchanged.

## 8. Next step

Review the current Phase 1 files with `CODE_REVIEW_GUIDE.md`. Phase 2 (agent registry) remains the next implementation phase; Phase 3 introduces framework execution. No later phase was started automatically.
