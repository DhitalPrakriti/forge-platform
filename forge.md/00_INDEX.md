# FORGE Engineering Specification Pack

**Project:** FORGE — AI Agent Platform Control Plane  
**Version:** 0.4

**Purpose:** Source-of-truth architecture and implementation pack for human + Codex development.

## Canonical Product Statement

**FORGE is a production control plane for defining, staging, evaluating, deploying, operating, and rolling back AI agents.**

The agent itself is defined by:

- reasoning instructions;
- model configuration;
- tools;
- deterministic policies;
- workflow/runtime behavior.

FORGE adds the production layer:

- immutable versioning;
- staging;
- evaluations;
- regression comparison;
- release gates;
- deployment;
- runtime durability;
- observability;
- rollback.

## Canonical Lifecycle

```text
DEFINE AGENT
    ↓
CREATE IMMUTABLE VERSION
    ↓
STAGING
    ↓
PLAYGROUND / DRY-RUN TESTING
    ↓
AUTOMATED EVALUATION
    ↓
REGRESSION COMPARISON
    ↓
RELEASE GATE
    ↓
PASS?
 ┌──┴──┐
 NO    YES
 │      │
BLOCK  APPROVE
        ↓
      DEPLOY
        ↓
   PRODUCTION
        ↓
     OBSERVE
        ↓
    HEALTHY?
  ┌────┴────┐
 YES        NO
  │          │
 KEEP     ROLLBACK
```

## Read Order

1. `01_PRODUCT_VISION.md`
2. `02_SYSTEM_ARCHITECTURE.md`
3. `03_AGENT_DEFINITION_AND_REGISTRY.md`
4. `04_RUNTIME_AND_STATE_MACHINE.md`
5. `05_TOOLS_POLICIES_APPROVALS.md`
6. `06_STAGING_EVALUATION_RELEASE_DEPLOY_ROLLBACK.md`
7. `07_DATABASE_SCHEMA.md`
8. `08_API_CONTRACT.md`
9. `09_OBSERVABILITY_RELIABILITY_SECURITY.md`
10. `10_CODEX_WORKING_RULES.md`
11. `11_PHASED_IMPLEMENTATION_PLAN.md`

## Non-Negotiable Architecture Rules

1. FORGE is a platform, not one support agent.
2. V1 uses a FORGE-owned runtime and state machine. LangChain/LangGraph are not required dependencies.
3. Agent versions are immutable.
4. PostgreSQL is durable truth.
5. Redis is coordination/cache, never the only durable source of important state.
6. LLMs never make authorization decisions.
7. Tool calls always pass validation and deterministic policy.
8. High-impact tool calls may require human approval.
9. A deployment points to one exact immutable agent version.
10. Evaluation artifacts are versioned and reproducible.
11. Release gates can block production promotion.
12. Rollback changes the production version pointer; it does not mutate history.
13. Every run records exact agent/model/tool/policy versions.
14. Irreversible tool actions must be idempotent.
15. Start as a modular monolith + worker, not microservices.

## First Demo

The first demo is a customer-support agent because it makes the platform easy to understand. The actual product is FORGE.

## Resolved Architecture Decisions

Read `12_ARCHITECTURE_DECISIONS.md` alongside the relevant phase specification. These decisions clarify V1 behavior; they do not authorize implementing later phases.

## Runtime and Review Guides

- `14_FORGE_RUNTIME_DECISION.md`: current runtime ownership, persistence, and phase integration.
- `13_LANGCHAIN_LANGGRAPH_RUNTIME.md`: superseded adoption record only.
- `../docs/CODE_REVIEW_GUIDE.md`: directory map and session review order.
- `FORGE_FRONTEND_SPEC.md`: full frontend blueprint and the current local testing slice.
- `../docs/FRONTEND_LOCAL_CONSOLE_SESSION.md`: supported F1–F3 implementation, review map, and verification.
- `../docs/PHASE_4_IMPLEMENTATION_REPORT.md`: local Tool Hub, bounded model/tool loop, console extension, and review walkthrough.

- [Phase 5 implementation and review](../docs/PHASE_5_IMPLEMENTATION_REPORT.md)
