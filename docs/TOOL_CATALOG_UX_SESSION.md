# Tool catalog and agent permission UX — 2026-09-19

## What changed

The workspace Tool Hub and immutable-version editor now share a searchable capability catalog. Previously, long technical names and UUIDs dominated a tall, ungrouped list. Registered tools now appear in a compact responsive grid, alphabetically ordered, with readable names, purpose, source, approval requirements, status, revision summary, and usage guidance.

Filters distinguish Code review, Customer service demos, and other Connected capabilities, plus Built-in versus MCP sources. The known `inspect_code` MCP example is grouped with Python inspection; arbitrary MCP tools remain connected capabilities rather than guessing their domain. Friendly names are presentation only: the exact tool ID, alias, revision and schema still govern permissions and execution.

Selection mode shows selected count, removable selection chips, selected-only filtering and an overlap reminder. Searching/filtering never removes permissions. Disabled tools cannot be newly selected; disabled selections on a clone can be removed. Missing pinned revisions remain visible through the existing unavailable-revision control. Every new selection is saved to the existing immutable-version API.

Technical details are expandable and include full ID/alias/revision, handler, risk, timeout, retry safety, idempotency and input/output schemas. Long MCP hashes and IDs no longer dominate the default view. Refund policy controls appear only when a refund tool is selected or a clone already has policy bindings; existing bindings remain reviewable. Policy IDs are available in their own technical details.

The workspace catalog consolidates registered built-in and MCP tools. Adding built-ins, discovering/registering MCP tools, and registering the demo refund policy live in separate expandable sections. All tool disable actions now use the same confirmation dialog, including MCP tools, because they affect every agent version in the workspace. Credentials and backend connection configuration remain server-side.

## How an agent uses multiple tools

1. Register capabilities in the workspace.
2. Select only relevant capabilities in a new agent version. For code review, use the Code review filter and usually select one inspection implementation rather than both equivalent built-in and MCP versions.
3. Write instructions specifying when to inspect code and how to use the result. Selection grants permission; it does not force calls or prescribe their order.
4. The model receives allowed tool descriptions/schemas and proposes a name plus arguments. FORGE checks exact bindings, input schema, policy, runtime limits and approval requirements before execution.
5. Results return to the model, which can request another allowed tool or answer. The run inspector preserves individual tool requests/results and model calls.

This change does not invent tools from prompts, execute arbitrary pasted code, add repository/file access, change model orchestration, or connect new business services. Those require actual registered capabilities and separate implementation. Search and categorization are UI conveniences, never authorization.

## Changed files and reading order

| File | Responsibility |
| --- | --- |
| `web/lib/tool-presentation.ts` | Shared readable names, purpose/source/approval guidance and matching; consumes existing tool metadata and builtin labels. |
| `web/components/tools/tool-catalog.tsx` | Search, filters, selected count/chips, disabled-state handling, cards and expandable technical evidence; accepts controlled selection callbacks or workspace actions. |
| `web/components/tools/tools-screen.tsx` | Workspace catalog, API registration/toggle mutations, grouped setup sections and shared disable confirmation. |
| `web/components/tools/mcp-tools.tsx` | Focuses on discovery/registration; registered tools are managed through the shared catalog instead of duplicated here. |
| `web/components/agents/version-form.tsx` | Wires catalog selection into existing react-hook-form values; conditionally exposes refund policy and hides IDs in details. |
| `web/app/globals.css` | Responsive capability cards, search controls, selected chips and compact section styling. |
| `web/tests/tool-catalog.test.tsx` | Verifies combined filtering preserves selections, removal updates counts, inactive tools are disabled, technical details start collapsed, and empty search state. |
| `web/tests/e2e/console.spec.ts` | Updates browser flows for expandable setup sections and readable registration confirmations, while retaining real API/worker/tool checks. |
| `forge.md/FORGE_FRONTEND_SPEC.md` | Records the implemented catalog scope. |
| `docs/CODE_REVIEW_GUIDE.md` | Adds review route and important state/permission boundaries. |
| `docs/TOOL_CATALOG_UX_SESSION.md` | This session report. |

Read presentation helper → shared catalog → version form → workspace/MCP registration → tests. Example: filter Code review, select Python inspection, filter to MCP, observe the existing selection chip remains, save version; the API still receives the selected tool UUID, not its display name.

## Dependencies, migration and checks

No dependencies, backend changes, migrations or paid model calls. Existing workspace data, versions and permissions are preserved. Unrelated `.env.example` and database-session edits plus generated instruction files remain outside this commit.

Commands use Node 22 in `web/`: `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`, and `npm run test:e2e`. Unit tests: 24 passed. Typecheck, lint and production build passed. Browser verification uses fake providers on the separate port-8001 backend, disposable test database and Redis DB 1, including the real local MCP example and approval flow. Browser results and visual verification are recorded after completion below.

Limitations: the existing API returns up to 100 registered tools; filters operate on that loaded catalog. MCP server display names are not exposed by the existing ToolRead response, so cards honestly say MCP server and retain the exact alias in technical details. Categories are curated presentation rules, not AI recommendations. Per-agent instruction presets, arbitrary custom tool creation and new business integrations are not part of this UI change.

Next: refresh Tool Hub, filter Code review and review the new cards; clone a version to adjust tool permissions. Test its behavior through a run and inspect actual tool evidence. No later phase was started automatically.

Final verification: all 11 browser scenarios passed across the full run (10 passed) and targeted MCP rerun (1 passed). The initial MCP test found an ambiguous accessible label between server selection and the new source filter; explicit accessible names and an exact test locator resolved it. Desktop catalog and mobile MCP screenshots were visually inspected; browser tests assert no horizontal overflow. Final lint and all 24 unit tests passed. Local `/tools` returns HTTP 200; refresh the existing development console to see changes.
