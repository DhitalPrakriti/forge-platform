# FORGE Frontend Specification

**Project:** FORGE — AI Agent Platform Control Plane  
**Document:** Frontend Product + UX + Engineering Specification  
**Purpose:** Source-of-truth frontend blueprint for implementation with Codex  
**Status:** Full product blueprint; local testing slice implemented (see scope below)  
**Primary audience:** Developer building the FORGE web control plane  
**Frontend goal:** Build a polished, dynamic, production-style interface for creating, staging, evaluating, deploying, observing, and rolling back AI agents.

---

## Current implementation scope — local testing console

The developer requested an earlier frontend to make the existing Phase 3 backend easier to test than Swagger. This authorizes the supported parts of F1–F3 before the original backend roadmap reaches its frontend phase. It does **not** imply completion of all F1–F3 requirements or the future control plane described below.

The current implementation lives in `web/`. The initial session record is `docs/FRONTEND_LOCAL_CONSOLE_SESSION.md`; the Phase 4 tool extension is documented in `docs/PHASE_4_IMPLEMENTATION_REPORT.md`.

| Area | Available now | Deferred dependency |
| --- | --- | --- |
| Foundation | Next.js/TypeScript, Tailwind, locally owned shadcn-style primitives, query/form layers, responsive shell, API readiness | Authentication and production organization membership |
| Workspace | Create organization; connect an existing UUID once; choose previously connected workspaces | Server-side organization listing |
| Agents | Paginated registry, create identity, agent detail | Advanced search, editing UI, aggregate metrics |
| Versions | Create immutable draft, select registered tool revisions, inspect, clone, confirmed archive | Staging, evaluation binding editors, deployment |
| Playground | One-message model/tool execution, explicit fake-tool examples | Multi-turn user conversation, external tools, mode selection |
| Runs | Open a run, output, sequence-ordered paginated events, model/tool-call evidence, active-run polling | Organization-wide run listing, SSE, replay, cancellation |
| Tools | Register installed demo revisions, inspect schemas, confirm disable/re-enable | Custom integrations, business policies, approvals |
| Overview | Backend readiness, first-page agent count, registry shortcuts | Production metrics, charts, alerts |

### Binding rules for this slice

- “Workspace” means the existing organization record. The console automatically supplies `X-Organization-ID`; this local header is **not authentication**.
- There is no organization-list endpoint. Only organizations explicitly created or connected in this browser appear in the picker; connecting verifies the record with the API.
- There is no run-list endpoint. The Runs page explicitly labels its browser-local history (up to 50 IDs per organization); details always come from the backend. Prompt/output content is not written to browser storage.
- Every organization-scoped query key includes the organization ID. Changing workspace remounts screen state and does not reuse another workspace’s data.
- Agent identity and version configuration are separate saves. Goal, instructions, model, and limits belong to the immutable version, not to agent identity.
- New versions use `standard-agent-v1` and may select active registered tool revisions. Clones preserve those selections by default and allow changes only in the new version. Policy/fallback/evaluation editors remain deferred.
- Backend configuration chooses fake or Gemini execution. The console never requests a provider API key or presents an unsupported runtime-mode switch. Fake results are visibly marked; unknown costs remain “Not available.”
- Budget settings are saved but **not enforced yet; planned for Phase 7**. Model timeout may be lower than the saved runtime limit.
- Run creation currently waits for execution. The console displays a waiting state until it receives the run ID, then opens the inspector. It does not pretend to stream during that initial wait.
- A failed transport can leave a run accepted on the backend. “Retry same request” retains the original request and idempotency key while this page remains open; it does not create a fresh key automatically. Reloading/navigation loses this in-memory retry context.
- Archive requires confirmation. Version configuration cannot be edited. The UI does not invent staging, evaluation, deployment, cancel, or release-override actions.
- Any later “override” examples in this blueprint are future design proposals, not an authorization to bypass FORGE release gates.
- Browser requests go through a restricted, same-origin Next.js route to the existing FastAPI contract. The initial console needed no backend changes; the Phase 4 backend now supplies its versioned tool registry, tool-call endpoint, and migration.
- This console runs on loopback for development. Production authentication and authorization remain backend prerequisites before exposing it beyond local development.

The Phase 4 Tools UI supports only the three installed local demos, not the eventual custom-integration catalog. The inspector separates model invocations from model-requested tool calls. Registration and disable controls call the backend; permission enforcement never lives in the browser. Fake examples only fill the input box and still pass through the real Tool Hub.

The remaining numbered sections describe the eventual product unless included in the table above.

---

# 1. Frontend Product Goal

The FORGE frontend should make a complex AI platform feel understandable.

A user should be able to:

```text
Create agent
→ Configure models/tools/policies
→ Create immutable version
→ Test in staging
→ Run evaluations
→ Compare regression
→ Pass release gate
→ Deploy
→ Observe production
→ Roll back if necessary
```

The frontend is not a generic chatbot UI.

It is an **AI operations control plane**.

---

# 2. Frontend Product Principles

## 2.1 Clarity over visual noise

The user should always know:

```text
Which agent?
Which version?
Which environment?
Which deployment?
Which run?
Which status?
```

Do not hide important system state.

## 2.2 Status must be visible everywhere

Use consistent badges for:

```text
DRAFT
STAGING
EVALUATING
APPROVED
PRODUCTION
DEPRECATED
ARCHIVED

RUNNING
WAITING_FOR_APPROVAL
COMPLETED
FAILED
CANCELLED
TIMED_OUT

PASS
FAIL
BLOCKED
HEALTHY
DEGRADED
```

## 2.3 Production actions must feel deliberate

Actions like:

```text
Deploy
Rollback
Approve high-risk tool call
Disable production deployment
Override release gate
```

must require explicit confirmation.

## 2.4 The platform should feel alive

Dynamic UI should include:

- live run status;
- streaming event timeline;
- deployment health updates;
- pending approvals;
- evaluation progress;
- release-gate results;
- cost updates;
- tool/model call timelines.

---

# 3. Recommended Frontend Stack

Use:

```text
Next.js
TypeScript
React
Tailwind CSS
shadcn/ui
TanStack Query
React Hook Form
Zod
Recharts
Lucide icons
```

Optional:

```text
TanStack Table
SSE for live run events
WebSocket later if needed
```

Do not add a large state-management library unless real global client state requires it.

---

# 4. Architecture Philosophy

Use the backend API as the source of truth.

Frontend state categories:

```text
Server state
→ TanStack Query

Form state
→ React Hook Form

URL state
→ route params/search params

Local UI state
→ React state
```

Avoid duplicating backend entities into a global frontend store.

---

# 5. Primary Navigation

Desktop sidebar:

```text
FORGE

Overview

Agents
Runs
Approvals
Evaluations
Deployments

Tools
Policies

Observability

Settings
```

Recommended first release:

```text
Overview
Agents
Runs
Approvals
Evaluations
Deployments
Tools
```

Policies can initially live inside Agent Version configuration.

---

# 6. Application Shell

Layout:

```text
┌───────────────────────────────────────────────────────────────┐
│ Top Bar                                                       │
│ Workspace | Search | Environment | Notifications | Profile    │
├───────────────┬───────────────────────────────────────────────┤
│               │                                               │
│ Sidebar       │ Main Content                                  │
│               │                                               │
│ Overview      │                                               │
│ Agents        │                                               │
│ Runs          │                                               │
│ Approvals     │                                               │
│ Evaluations   │                                               │
│ Deployments   │                                               │
│ Tools         │                                               │
│               │                                               │
└───────────────┴───────────────────────────────────────────────┘
```

---

# 7. Global Top Bar

Include:

```text
Organization / workspace selector
Environment selector
Global search
Pending approvals indicator
System health indicator
User menu
```

Environment selector:

```text
Development
Staging
Production
```

For V1, environment may primarily affect filtering.

---

# 8. Overview Dashboard

Route:

```text
/overview
```

Purpose:

> Give the user an immediate operational summary.

Header:

```text
Overview
Last 24 hours
Environment: Production
```

Top metric cards:

```text
Active Agents
Runs Today
Success Rate
Avg Cost / Run
P95 Latency
Pending Approvals
```

Example:

```text
Active agents      7
Runs today         4,821
Success            97.4%
Avg cost           $0.031
P95 latency        2.2s
Approvals          3
```

Charts:

- runs over time;
- successful vs failed;
- cost over time;
- model usage;
- fallback rate;
- top agents.

Alerts:

```text
3 approvals waiting
1 deployment degraded
2 failed release gates
Gemini fallback rate increased
```

Each alert should deep-link to the relevant page.

---

# 9. Agents Page

Route:

```text
/agents
```

Purpose:

> Browse and manage all agent definitions.

Table columns:

```text
Name
Description
Production Version
Lifecycle
Runs 24h
Success
Avg Cost
Last Updated
```

Actions:

```text
Open
Create Version
Open Playground
```

Primary CTA:

```text
+ Create Agent
```

---

# 10. Create Agent Flow

Route:

```text
/agents/new
```

Use a multi-step wizard.

Steps:

```text
1. Identity
2. Reasoning / Instructions
3. Models
4. Tools
5. Policies
6. Runtime Limits
7. Evaluation
8. Review
```

## Step 1 — Identity

Fields:

```text
Agent Name
Slug
Description
Goal
```

## Step 2 — Reasoning / Instructions

Fields:

```text
System Instructions
Behavior Notes
Expected Output Style
```

Use a large code/editor-style textarea.

Do not expose or store hidden model chain-of-thought. FORGE stores explicit instructions and observable execution events.

## Step 3 — Models

UI:

```text
Primary Model
[ Gemini ▼ ]

Fallback Models
[ OpenAI ▼ ]

Temperature
[ slider ]

Max output tokens
[ input ]
```

Show provider health:

```text
Gemini     Healthy
OpenAI     Healthy
```

Never expose provider secrets.

## Step 4 — Tools

Tool selector:

```text
Available Tools

[✓] web_search
[✓] read_url
[ ] send_email
[✓] search_documents
[ ] issue_refund
```

Each row shows:

```text
Description
Version
Risk
Status
```

## Step 5 — Policies

Example rule UI:

```text
Tool: issue_refund

IF amount <= 100
THEN ALLOW

IF amount > 100 AND amount <= 500
THEN REQUIRE_APPROVAL

IF amount > 500
THEN DENY
```

For V1 this can render backend-defined policy rules rather than a fully general visual policy language.

## Step 6 — Runtime Limits

```text
Max Steps
Max Model Calls
Max Tool Calls
Max Runtime
Max Cost / Run
```

Example:

```text
Max steps:           12
Max model calls:     10
Max tool calls:      20
Max runtime:         120s
Max cost/run:        $0.25
```

## Step 7 — Evaluation

Choose evaluation suite.

Show:

```text
Production deployment requires a passing release gate.
```

## Step 8 — Review

Summary:

```text
Company Research Agent

Primary Model: Gemini
Fallback: OpenAI
Tools: 4
High-risk tools: 0
Max cost: $0.20/run
Evaluation: company-research-v1
```

CTA:

```text
Create Agent Version
```

---

# 11. Agent Detail Page

Route:

```text
/agents/[agentId]
```

Header:

```text
Support Agent
Customer support and billing resolution

Production: v2.1
[Open Playground]
[Create Version]
```

Tabs:

```text
Overview
Versions
Runs
Tools
Evaluation
Deployments
```

Overview cards:

```text
Production Version
Runs 24h
Success Rate
P95 Latency
Avg Cost
Fallback Rate
```

---

# 12. Versions UI

Versions table:

```text
Version
Lifecycle
Model
Tools
Evaluation
Release Gate
Created
```

Example:

```text
v2.2    STAGING      Gemini     5    PASS    PASS
v2.1    PRODUCTION   Gemini     5    PASS    PASS
v2.0    DEPRECATED   Gemini     4    PASS    PASS
```

Version detail route:

```text
/agents/[agentId]/versions/[versionId]
```

Tabs:

```text
Configuration
Playground
Evaluation
Release
Runs
```

Immutable version notice:

```text
This version is immutable.
To make changes, create a new version.

[Create New Version from v2.2]
```

Future version diff:

```text
v2.1 → v2.2
Prompt changed
Fallback model added
Tool removed
Max cost changed
```

---

# 13. Playground

Route:

```text
/agents/[agentId]/versions/[versionId]/playground
```

This should be one of FORGE's strongest screens.

Layout:

```text
┌────────────────────────┬──────────────────────────────────────┐
│ Input / Conversation   │ Run Inspector                        │
│                        │                                      │
│ User input             │ Status                               │
│ Agent response         │ Timeline                             │
│                        │ Model Calls                          │
│                        │ Tool Calls                           │
│                        │ Policies                             │
│                        │ Cost                                 │
└────────────────────────┴──────────────────────────────────────┘
```

Modes:

```text
Chat
Structured JSON
```

Execution mode:

```text
DRY_RUN
LIVE
```

Staging should default to `DRY_RUN` for side-effecting tools.

---

# 14. Live Run Experience

As a run executes:

```text
RUNNING

✓ Gemini call
✓ web_search
✓ read_url
• Gemini call...
```

Prefer SSE for live event updates.

Run inspector fields:

```text
Run ID
Status
Agent Version
Current Step
Model Calls
Tool Calls
Total Cost
Elapsed Time
Trace ID
```

---

# 15. Event Timeline

Example:

```text
8:31:03 PM  Run started
8:31:04 PM  Gemini completed
8:31:04 PM  Tool requested: web_search
8:31:05 PM  Tool completed
8:31:06 PM  Gemini completed
8:31:07 PM  Run completed
```

Event categories:

```text
model
tool
policy
approval
retry
error
complete
```

---

# 16. Model Call Inspector

Click a model event:

```text
Provider: Gemini
Model: gemini-...
Latency: 843 ms
Input tokens: 740
Output tokens: 312
Cost: $0.004
Status: SUCCESS
Fallback: No
```

Do not expose hidden chain-of-thought.

---

# 17. Tool Call Inspector

Example:

```text
Tool: issue_refund

Arguments:
{
  "customer_id": 4831,
  "amount": 425
}

Risk: HIGH
Policy: REQUIRE_APPROVAL
Status: WAITING_FOR_APPROVAL
```

Show the exact policy reason.

---

# 18. Runs Page

Route:

```text
/runs
```

Table:

```text
Run ID
Agent
Version
Environment
Status
Started
Latency
Cost
```

Filters:

```text
Agent
Status
Environment
Version
Date range
Cost range
```

Status semantics:

```text
RUNNING               active/info
WAITING_FOR_APPROVAL  warning
COMPLETED             success
FAILED                danger
CANCELLED             neutral
TIMED_OUT             danger
```

---

# 19. Run Detail Page

Route:

```text
/runs/[runId]
```

Header:

```text
run_8f92a1
Support Agent
v2.1
PRODUCTION
COMPLETED
```

Actions:

```text
Replay
Retry
Cancel
Copy Run ID
```

Only show actions valid for the run's current state.

Tabs:

```text
Timeline
Input / Output
Models
Tools
Evaluation
Raw Events
```

Summary cards:

```text
Status
Duration
Cost
Model Calls
Tool Calls
Fallbacks
```

Execution tree:

```text
Run
├── Gemini
├── lookup_customer
├── Gemini
├── issue_refund
│   └── Approval
├── issue_refund executed
└── Gemini
```

This is a UI visualization, not a graph database.

---

# 20. Approvals Page

Route:

```text
/approvals
```

Table/cards:

```text
Agent
Action
Risk
Requested Value
Requested At
Expires
Status
```

Example:

```text
Support Agent
Issue Refund
HIGH
$425 CAD
Expires in 12m
PENDING
```

---

# 21. Approval Detail

Modal or page:

```text
Agent: Support Agent v2.1
Run: run_8293
Tool: issue_refund

Customer: 4831
Amount: $425 CAD

Policy:
Refund > $100 requires human approval

[DENY]
[APPROVE]
```

Require explicit confirmation.

After approval:

```text
Approved
The run has been queued to resume.
[View Run]
```

Do not optimistically show approval success before backend confirmation.

---

# 22. Evaluations Page

Route:

```text
/evaluations
```

Sections:

```text
Evaluation Suites
Recent Evaluation Runs
Failed Evaluations
```

Suite detail shows:

```text
Name
Version
Cases
Metrics
Last Run
```

---

# 23. Evaluation Run Page

Route:

```text
/evaluations/runs/[evaluationRunId]
```

During execution:

```text
Support Agent v2.2
Evaluation: support-regression-v3

RUNNING 43 / 100
[progress bar]
```

Summary metrics:

```text
Task Success
Tool Correctness
Policy Compliance
Avg Cost
P95 Latency
```

Case table:

```text
Case
Status
Task Score
Tool Score
Cost
Latency
```

Failed cases should deep-link to their underlying run details.

---

# 24. Regression Comparison

Candidate vs production baseline:

```text
                    Production v2.1   Candidate v2.2

Task success             92%               95%
Tool correctness         97%               96%
Policy compliance       100%              100%
Avg cost               $0.031            $0.047
P95 latency              2.1s              1.9s
```

Show:

```text
absolute value
delta
threshold
pass/fail
```

---

# 25. Release Gate UI

Card:

```text
Release Gate

Task Success         PASS
Tool Correctness     PASS
Policy Compliance    PASS
Average Cost         PASS
P95 Latency          PASS

OVERALL
PASS
```

If failed:

```text
RELEASE BLOCKED
```

Always show exact thresholds.

Example:

```text
Tool correctness
94.1%
Required: >= 95%
FAIL
```

---

# 26. Deploy UX

Deploy button enabled only if backend confirms the version is eligible.

Confirmation:

```text
Deploy Support Agent v2.2 to Production?

Current Production:
v2.1

New Production:
v2.2

Release Gate:
PASS

[Cancel]
[Deploy v2.2]
```

Deployment is a pointer to an immutable version.

---

# 27. Deployments Page

Route:

```text
/deployments
```

Table:

```text
Agent
Environment
Active Version
Health
Runs 24h
Error Rate
Last Change
```

---

# 28. Deployment Detail

Route:

```text
/deployments/[deploymentId]
```

Header:

```text
Support Agent / Production
v2.2
HEALTHY
```

Actions:

```text
Rollback
Disable
View Version
```

Health cards:

```text
Success Rate
Error Rate
Fallback Rate
Tool Failure Rate
Avg Cost
P95 Latency
```

Charts:

```text
runs over time
errors
cost
latency
fallback rate
```

---

# 29. Deployment History

Timeline:

```text
Sep 7 8:12 PM
v2.2 deployed

Sep 6 4:10 PM
v2.1 deployed

Sep 5 9:02 PM
v2.0 rolled back to v1.9
```

Show actor and reason when available.

---

# 30. Rollback UX

Rollback confirmation must be extremely clear.

```text
Rollback Production Agent?

Current:
v2.2

Target:
v2.1

Reason:
[________________________________]

New runs will immediately use v2.1.
Existing runs stay on the version they started with.

[Cancel]
[Rollback to v2.1]
```

After success:

```text
Rollback completed.
Production now points to v2.1.
```

Refresh:

```text
deployment
agent production version
deployment history
health metrics
```

---

# 31. Tools Page

Route:

```text
/tools
```

Table:

```text
Tool
Version
Risk
Used By
Timeout
Retry Safe
Status
```

Tool detail:

```text
Schema
Configuration
Used By Agents
Recent Calls
Failures
```

Never expose tool secrets.

---

# 32. Observability Page

Route:

```text
/observability
```

Can be V1.5 if overview/run detail already covers the important telemetry.

Global metrics:

```text
Runs
Latency
Cost
Model Calls
Tool Calls
Errors
Fallbacks
```

Filters:

```text
Agent
Version
Environment
Provider
Time window
```

---

# 33. Notifications

Notification center should surface:

```text
approval requested
release gate completed
release gate failed
deployment degraded
rollback completed
evaluation completed
```

V1 can poll.

Later use SSE/WebSocket for global notifications.

---

# 34. Dynamic Data Strategy

Use TanStack Query.

Example query keys:

```text
["agents"]
["agent", agentId]
["agentVersions", agentId]
["run", runId]
["runEvents", runId]
["approvals"]
["evaluationRun", evaluationRunId]
["deployments"]
["deployment", deploymentId]
```

Cache invalidation examples:

```text
create agent
→ invalidate agents

create version
→ invalidate versions

approve request
→ invalidate approval + run

deploy
→ invalidate deployment + agent + versions

rollback
→ invalidate deployment + history + agent
```

---

# 35. Real-Time Updates

Prefer SSE for run events.

Concept endpoint:

```text
GET /api/v1/runs/{runId}/stream
```

Events:

```text
run.status_changed
run.event_created
tool.requested
approval.requested
run.completed
run.failed
```

Fallback:

```text
poll every 1–2 seconds while active
stop polling at terminal state
```

---

# 36. Form Validation

Use:

```text
React Hook Form
+
Zod
```

Client validation mirrors backend constraints where practical.

Backend remains authoritative.

---

# 37. UI State Requirements

Every major page needs:

```text
loading
empty
success
error
permission denied
partial data
```

Examples:

```text
No agents yet.
Create your first agent to begin building with FORGE.
[Create Agent]
```

```text
Unable to load run details.
Trace ID: tr_98321
[Retry]
```

Use skeletons for initial data loading.

---

# 38. Optimistic Update Rules

Safe-ish:

```text
minor metadata
UI preferences
```

Do not optimistically update critical operations:

```text
approval
deployment
rollback
release gate override
```

Wait for server confirmation.

---

# 39. Confirmation Dialogs

Required for:

```text
Deploy Production
Rollback
Deny Approval
Archive Version
Disable Deployment
Release Gate Override
```

---

# 40. Responsive Strategy

Desktop-first.

Primary breakpoints should support:

```text
1440+
1280
1024
tablet
```

Mobile V1 may support:

```text
view run
view health
approve/deny
```

Do not prioritize complex configuration workflows on mobile.

---

# 41. Visual Design Direction

FORGE should feel like:

```text
developer tool
AI operations console
cloud platform
production control plane
```

Not:

```text
social app
marketing page
generic chatbot
```

Use:

- dense but readable layout;
- clear technical hierarchy;
- restrained motion;
- subtle borders;
- monospaced IDs;
- strong status semantics;
- clean charts;
- inspector panels/drawers;
- structured tables.

---

# 42. Semantic Status Design

Use design-system semantic tokens.

```text
Success / Healthy / Pass
Danger / Failed / Denied
Warning / Waiting / Approval
Info / Running
Neutral / Draft / Archived
```

Do not rely on color alone; always include text/icon.

---

# 43. Typography

Use:

```text
Sans-serif → UI
Monospace → IDs / JSON / model names / traces / tool args
```

---

# 44. Motion

Minimal motion only:

```text
running status pulse
progress transitions
modal/drawer transition
timeline event appearance
```

Avoid decorative motion.

---

# 45. Core Reusable Components

```text
AppShell
Sidebar
TopBar

StatusBadge
EnvironmentBadge
RiskBadge

MetricCard
HealthCard

DataTable
EmptyState
ErrorState
LoadingSkeleton

AgentCard
VersionCard
DeploymentCard

RunTimeline
RunEventRow
ToolCallPanel
ModelCallPanel

ApprovalCard
ApprovalDialog

ReleaseGateCard
RegressionTable

CostChart
LatencyChart
RunsChart

JsonViewer
CodeBlock
CopyButton

ConfirmDialog
```

---

# 46. Suggested Folder Structure

```text
web/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   ├── agents/
│   │   ├── page.tsx
│   │   ├── new/page.tsx
│   │   └── [agentId]/
│   │       ├── page.tsx
│   │       └── versions/
│   │           └── [versionId]/
│   │               ├── page.tsx
│   │               └── playground/page.tsx
│   ├── runs/
│   ├── approvals/
│   ├── evaluations/
│   ├── deployments/
│   ├── tools/
│   └── observability/
├── components/
│   ├── layout/
│   ├── agents/
│   ├── runs/
│   ├── approvals/
│   ├── evaluations/
│   ├── deployments/
│   ├── tools/
│   └── ui/
├── lib/
│   ├── api/
│   ├── query/
│   ├── schemas/
│   ├── utils/
│   └── constants/
├── hooks/
├── types/
└── public/
```

---

# 47. API Client Layer

Do not scatter `fetch()` across components.

Create:

```text
lib/api/client.ts
lib/api/agents.ts
lib/api/runs.ts
lib/api/approvals.ts
lib/api/evaluations.ts
lib/api/deployments.ts
lib/api/tools.ts
```

Example:

```ts
export async function getRun(runId: string): Promise<Run> {
  return apiClient.get(`/api/v1/runs/${runId}`);
}
```

---

# 48. Type Safety

Prefer OpenAPI-generated frontend types later.

V1 may use TypeScript types + Zod schemas.

Key enums:

```ts
type AgentLifecycle =
  | "DRAFT"
  | "STAGING"
  | "EVALUATING"
  | "APPROVED"
  | "PRODUCTION"
  | "DEPRECATED"
  | "ARCHIVED";

type RunStatus =
  | "CREATED"
  | "QUEUED"
  | "RUNNING"
  | "WAITING_FOR_TOOL"
  | "WAITING_FOR_APPROVAL"
  | "RETRYING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED"
  | "TIMED_OUT";

type PolicyDecision =
  | "ALLOW"
  | "DENY"
  | "REQUIRE_APPROVAL";
```

---

# 49. Authentication and Secrets

Frontend needs:

```text
login
protected routes
session
workspace context
```

Never store in browser local storage:

```text
provider API keys
tool secrets
OAuth refresh tokens
service credentials
```

Frontend sees only safe status/configuration metadata.

---

# 50. Accessibility

Support:

- keyboard navigation;
- visible focus;
- semantic headings;
- accessible dialogs;
- table headers;
- labels for icons;
- color-independent status states;
- ARIA where needed.

---

# 51. Frontend Testing

Recommended:

```text
Vitest
React Testing Library
Playwright
```

Component tests:

```text
StatusBadge renders all states
ReleaseGateCard shows failed thresholds
ApprovalDialog disables while submitting
RunTimeline orders events correctly
RollbackDialog shows correct target version
```

E2E flows:

```text
Create agent → create version
Run waits → approve → resumes
Evaluate → gate pass → deploy
Production v2 → rollback → v1 active
```

---

# 52. Frontend Phase Plan

## Phase F1 — Foundation

```text
Next.js
TypeScript
Tailwind
shadcn/ui
TanStack Query
AppShell
Sidebar
TopBar
API client
error/loading patterns
```

## Phase F2 — Agents

```text
Agents list
Create Agent wizard
Agent detail
Versions
Version detail
```

## Phase F3 — Playground + Runs

```text
Playground
Create run
Live status
Timeline
Model inspector
Tool inspector
```

## Phase F4 — Approvals

```text
Approvals page
Approval detail
Approve/deny
Live run resume
```

## Phase F5 — Evaluations

```text
Evaluation suites
Evaluation run progress
Metrics
Case results
```

## Phase F6 — Release

```text
Regression comparison
Release gate
Deploy eligibility
```

## Phase F7 — Deployment + Rollback

```text
Deployments list
Deployment detail
Health
History
Rollback
```

## Phase F8 — Observability

```text
Overview charts
Cost
Latency
Fallbacks
Failures
```

## Phase F9 — Polish

```text
Global search
Notifications
Responsive layout
Accessibility
Keyboard shortcuts
Better empty/error states
```

---

# 53. First Frontend Vertical Slice

Do not build every page immediately.

Build this first:

```text
Agents List
→ Agent Detail
→ Version Detail
→ Playground
→ Start Run
→ View Live Run Timeline
```

Then add approval.

This creates something demonstrable early.

---

# 54. Killer Portfolio Demo

The finished frontend should make this story visible:

```text
1. Open Agents.
2. Create Support Agent.
3. Create v1.
4. Configure Gemini + fallback.
5. Attach tools.
6. Configure refund policy.
7. Open staging playground.
8. Run duplicate-charge request.
9. Run pauses at $425 refund.
10. Open Approvals.
11. Approve.
12. Run resumes live.
13. Inspect model/tool trace and cost.
14. Create v2.
15. Run evaluation suite.
16. Compare v1 vs v2 regression.
17. Release gate passes.
18. Deploy v2 to production.
19. View production health.
20. Simulate/develop an issue.
21. Roll back to v1.
22. Deployment history confirms recovery.
```

This explains FORGE visually without requiring a long presentation.

---

# 55. Information Hierarchy

Each screen answers one main question:

```text
Overview
→ Is FORGE healthy?

Agents
→ What agents exist?

Agent Detail
→ How is this agent configured/performance?

Version Detail
→ What exactly is this immutable version?

Playground
→ How does this version behave?

Runs
→ What happened during execution?

Approvals
→ What needs human action?

Evaluation
→ Is this version good enough?

Release
→ Is this version eligible for production?

Deployments
→ What version is serving users?

Rollback
→ How do I recover from a bad deployment?
```

---

# 56. Important UX Rules

## Immutable versions

```text
This version is immutable.
Create a new version to make changes.
```

## Production deploy

Always show:

```text
Agent
Version
Environment
Release Gate
Current Production
```

## Rollback

Always show:

```text
Current version
Target version
Effect on new runs
Effect on existing runs
Reason
```

## High-risk approval

Always show:

```text
Agent
Tool
Risk
Arguments
Policy reason
Expiration
```

## Evaluation

Never show only PASS/FAIL.

Show:

```text
actual
threshold
result
```

## Failure

Answer:

```text
What failed?
Where?
Why?
Is retry safe?
What can user do next?
```

---

# 57. Do Not Build First

Avoid spending early time on:

```text
marketing landing page
3D graphics
animation-heavy hero screen
mobile app
drag-and-drop workflow designer
custom graph database visualization
full no-code builder
complex themes
```

The control plane itself is the valuable project.

---

# 58. Future Enhancements

Later:

```text
visual workflow editor
multi-agent topology
agent relationship explorer
canary deployment
shadow evaluation
deployment diff
real-time global notifications
public hosted agent page
embeddable agent widget
team collaboration
comments
audit log viewer
```

A future multi-agent visualization could show:

```text
Research Agent
├── delegates → Web Research Agent
├── delegates → Finance Agent
└── uses → Document Search
```

This visualization does not require a graph database in V1.

---

# 59. Codex Frontend Working Rules

Give Codex these rules:

```text
Read FORGE_FRONTEND_SPEC.md before frontend work.

- Use Next.js + TypeScript.
- Use Tailwind + shadcn/ui.
- Use TanStack Query for server state.
- Use React Hook Form + Zod for forms.
- Keep API calls in lib/api.
- Keep route pages thin.
- Build reusable domain components.
- Do not hardcode mock state once API exists.
- Do not add a global state library unless justified.
- Do not change backend contracts without discussing it.
- Support loading/error/empty states.
- Add tests for critical flows.
- Never expose secrets.
- Never display hidden chain-of-thought.
- Do not add unrelated future features.
```

---

# 60. Codex Prompt — Frontend Foundation

```text
Read:
- FORGE_FRONTEND_SPEC.md
- backend API specification

Implement only frontend Phase F1.

Requirements:
- Next.js + TypeScript
- Tailwind
- shadcn/ui
- application shell
- sidebar
- topbar
- route structure
- TanStack Query
- API client abstraction
- loading/error patterns
- responsive desktop-first layout

Do not implement agent forms or dashboards yet.

After implementation:
1. list files changed,
2. explain architecture,
3. run lint/typecheck/tests,
4. report results.
```

---

# 61. Codex Prompt — Agents UI

```text
Read FORGE_FRONTEND_SPEC.md.

Implement only:
- Agents list
- Create Agent flow
- Agent detail
- Versions list
- Version detail

Requirements:
- real API integration
- TanStack Query
- React Hook Form + Zod
- status badges
- loading/error/empty states
- immutable-version messaging
- component tests

Do not implement Playground yet.
```

---

# 62. Codex Prompt — Playground + Run Inspector

```text
Read FORGE_FRONTEND_SPEC.md.

Implement:
- Version Playground
- run creation
- live run status
- event timeline
- model call inspector
- tool call inspector
- policy events
- cost/latency summary

Prefer SSE if backend supports it.
Otherwise poll while the run is active.

Do not expose hidden model reasoning.
```

---

# 63. Codex Prompt — Approvals UI

```text
Read FORGE_FRONTEND_SPEC.md.

Implement:
- Approvals page
- pending approvals table
- approval detail
- risk/policy explanation
- approve
- deny
- confirmation dialogs
- link back to run
- refresh after action

Do not optimistically mark approval complete before backend confirms.
```

---

# 64. Codex Prompt — Evaluation + Release UI

```text
Read FORGE_FRONTEND_SPEC.md.

Implement:
- evaluation runs
- progress
- metric cards
- case results
- regression comparison
- release gate card
- blocked state
- deploy eligibility

Show exact threshold vs actual value.
```

---

# 65. Codex Prompt — Deployment + Rollback UI

```text
Read FORGE_FRONTEND_SPEC.md.

Implement:
- deployments list
- deployment detail
- production version
- health metrics
- deployment history
- deploy confirmation
- rollback confirmation
- rollback reason
- rollback success state

Existing runs must remain on the version they started with.
```

---

# 66. Final Frontend Mental Model

```text
FORGE FRONTEND

Overview
    ↓
Agent Builder
    ↓
Agent Registry
    ↓
Version Detail
    ↓
Staging Playground
    ↓
Run Inspector
    ↓
Evaluation
    ↓
Regression
    ↓
Release Gate
    ↓
Deployment
    ↓
Production Health
    ↓
Rollback
```

---

# 67. Final Frontend Statement

**The FORGE frontend is a dynamic AI operations console for creating versioned agents, testing them in staging, inspecting live execution, approving sensitive actions, evaluating quality, enforcing release gates, deploying production versions, monitoring operational health, and rolling back safely when a deployment breaks.**

The frontend succeeds when a developer can immediately answer:

```text
What agents exist?
What version is production?
What is running right now?
What needs approval?
What happened in this run?
How much did it cost?
Did the new version improve?
Can I deploy it?
Is production healthy?
Can I recover quickly?
```

---

**End of FORGE Frontend Specification**

## Phase 5 console extension

Tool Hub registers `issue_refund` and the installed refund policy. New versions select an exact policy revision alongside tool revisions. The run inspector shows approval amount/customer/hash/expiry/status/reviewer/reason and provides confirmed approve/deny followed by explicit resume. The reviewer token stays in component memory and clears on reload/workspace/run changes; the same-origin proxy forwards it only to decision/resume routes. Waiting runs poll. This is the supported local Phase 5 slice, not the full production approvals dashboard or login system.

## Phase 6 console behavior

Run creation receives 202/QUEUED and navigates to the inspector. The inspector polls QUEUED/RUNNING/RETRYING/tool/approval waits, displays worker progress, offers confirmed cancellation, and can create a linked retry when the server permits it. Approval confirmation schedules automatic continuation for queued runs; legacy runs retain explicit resume. Existing safety checks remain server-side. Full queue administration and production IAM are outside this console slice.
