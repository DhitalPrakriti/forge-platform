# FORGE Product Vision

## Problem

An AI agent prototype is easy:

```text
User → LLM → Tool → Answer
```

Production is difficult:

- Which version is running?
- What if the model times out?
- What if a worker crashes?
- What if a tool is dangerous?
- How do we pause for human approval?
- How do we avoid duplicate refunds on retry?
- How do we measure quality and cost?
- How do we prevent a bad prompt/model change from reaching production?
- How do we roll back immediately?

FORGE solves these operational problems.

## Thesis

> **Agent frameworks help developers build agents. FORGE helps developers operate agents.**

A developer can arrive with only an agent idea and define:

```text
name
purpose
instructions
models
tools
policies
limits
evaluation suite
```

FORGE supplies its own runtime and operations layer; no agent framework or graph database is required for V1.

## Example Definition

```yaml
name: company-research-agent

goal: Research companies and produce evidence-backed reports.

model:
  primary: gemini-2.5-flash
  fallbacks:
    - gpt-5-mini

tools:
  - web_search
  - read_url
  - search_documents
  - generate_report

limits:
  max_steps: 12
  max_runtime_seconds: 180
  max_cost_per_run_usd: 0.20

policies:
  external_email: deny
  payments: deny

evaluation:
  suite: company-research-v1
```

## How a Deployed Agent Is Used

V1 access methods:

1. **FORGE Playground** — developer/internal testing.
2. **REST API** — developer embeds the deployed agent in another application.

Later:

- hosted agent page;
- embeddable widget;
- Slack/Teams;
- webhooks;
- SDK adapters.

Typical production flow:

```text
End User
  ↓
Company Application
  ↓
FORGE API
  ↓
Production Deployment
  ↓
Exact Agent Version
  ↓
FORGE Runtime
  ↓
Models + Tools + Policies + Workflow
  ↓
Result
```

## V1 Positioning

FORGE is not:

- a chatbot builder;
- a LangGraph replacement;
- a vector database;
- a huge IAM suite;
- a one-off support agent.

FORGE is a production-oriented hosted runtime and operations control plane for agents.
