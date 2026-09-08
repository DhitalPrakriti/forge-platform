# Runtime decision reversal session — 2026-09-06

## 1. Scope completed

Reversed the previously approved LangChain/LangGraph architecture at the user's request. Restored FORGE-owned execution, state machine, PostgreSQL checkpoints, Tool Hub integration, provider adapters, and approval continuation. Kept review requirements and existing Phase 1/2 behavior intact. No runtime implementation started.

## 2. Files changed and review order

| File | Change |
| --- | --- |
| `forge.md/14_FORGE_RUNTIME_DECISION.md` (new) | Current ownership, execution walkthrough, persistence and phase scope; read first |
| `forge.md/12_ARCHITECTURE_DECISIONS.md` | Supersede decision 7, add decision 9, restore transactional FORGE checkpoint ownership |
| `forge.md/10_CODEX_WORKING_RULES.md` | Restore provider SDK adapters and FORGE runtime prompts; retain session review rules |
| `forge.md/04_RUNTIME_AND_STATE_MACHINE.md` | FORGE execution/checkpoint/resume semantics |
| `forge.md/07_DATABASE_SCHEMA.md` | Restore planned run_checkpoints table; remove mandatory vendor storage/thread IDs |
| `forge.md/05_TOOLS_POLICIES_APPROVALS.md` | FORGE Tool Hub and persisted approval continuation |
| `forge.md/11_PHASED_IMPLEMENTATION_PLAN.md` | FORGE runtime phases and direct provider adapters |
| `forge.md/02_SYSTEM_ARCHITECTURE.md` | Runtime ownership, diagram and stack |
| `forge.md/03_AGENT_DEFINITION_AND_REGISTRY.md` | Framework-neutral runtime ownership and compatibility references |
| `forge.md/01_PRODUCT_VISION.md` | FORGE-owned execution statement |
| `forge.md/00_INDEX.md` | Version 0.4 and current/historical design links |
| `forge.md/13_LANGCHAIN_LANGGRAPH_RUNTIME.md` | Prominent superseded marker; prior proposal preserved |
| `docs/LANGGRAPH_ADOPTION_SESSION.md` | Prominent superseded marker; original session results preserved |
| `docs/CODE_REVIEW_GUIDE.md` | Future runtime reading path now points to document 14 |
| `README.md` | Current architecture direction |
| `docs/FORGE_RUNTIME_REVERSAL_SESSION.md` (new) | This handoff |

Changed directories: `forge.md/`, `docs/`, and root README. Application source, test code, migrations, dependency files, CI, and Docker configuration did not change. Historical Phase 1/2 reports retain their original dated-session meaning; document 14 governs future implementation.

## 3. Dependencies and migrations

None added, removed, or edited. Framework packages were never installed. Existing immutable runtime template labels do not encode a LangGraph dependency and remain unchanged.

## 4. Tests added

None: documentation change only. Ran existing available tests as a regression check.

## 5. Commands

Read working rules and searched runtime references with `cat` and `rg`. Inspected `git status --short` and `git diff --stat`. Updated documents with `/tmp/forge_revert_runtime.py` and shell heredocs. Ran:

```sh
.tools/bin/uv run ruff check .
.tools/bin/uv run ruff format --check .
.tools/bin/uv run pytest -q
```

Checked local Markdown links and balanced fenced blocks with a Python script; checked remaining framework references for stale current instructions.

## 6. Results

Lint and formatting passed. Tests: **30 passed, 8 skipped**, with the two existing upstream test-library deprecation warnings. PostgreSQL integration tests skipped because FORGE_TEST_DATABASE_URL was not configured; no database was started for a documentation-only change. No hosted CI or Docker execution was performed.

## 7. Limits and review questions

Execution/recovery code remains future work; this change selects its owner, not a completed runtime. A PostgreSQL transaction does not cover an external tool effect, so idempotency/reconciliation remains mandatory. Review: who owns checkpoints now, what gets committed together, and what must be verified before an approved tool call resumes?

Changes remain local on dev; no commit/push or GitHub repository metadata change was made during this session.

## 8. Next step

Review document 14 → decisions → working rules → runtime/schema → phase plan. The execution walkthrough is in document 14. Phase 3 can begin upon instruction, using the FORGE-owned runtime design. Session review handoffs remain required.
