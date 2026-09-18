# Business tool ideas captured — September 18, 2026

Documentation-only session, requested by the user after discussing restaurant customer-service agents.

## Recorded direction

- Frontend service catalog and account connection, followed by capability review and tool selection.
- Reusable workspace connections with different permissions for different agents.
- Restaurant examples: menu lookup, availability, reservations, and order status.
- Existing MCP integrations where available; an API wrapper implemented once where needed.
- Optional model suggestions of existing capabilities, with explicit user selection and server-side authorization.
- Separate customer booking confirmation from platform permission/operator approval.
- Future policy-controlled reads, connection health/reconnection/revocation, and clear unsupported-service states.

These are planned product requirements. Existing MCP server configuration remains backend-managed, and every MCP call still requires approval. No restaurant provider, OAuth integration, API builder, or automatic tool implementation was added.

## Files and review order

1. `forge.md/FORGE_FRONTEND_SPEC.md`: target business-owner journey and current-versus-planned boundary.
2. `forge.md/05_TOOLS_POLICIES_APPROVALS.md`: integration responsibilities, reusable permissions, and restaurant execution example.
3. `docs/BUSINESS_TOOL_IDEAS_SESSION.md`: this session record.

No application files, dependencies, database migrations, or tests added. No caller/callee changes. Example future request walkthrough: availability lookup → real options → customer confirmation → policy/approval → booking → recorded outcome.

Validation: reviewed the Markdown additions for consistent current/planned wording and ran `git diff --check` on the three changed documents. Application tests were not run because runtime behavior is unchanged. Git operations: stage these documents only, commit, and push to `dev` under the standing workflow. Existing user edits and generated files are excluded.

Next step: retain this direction while completing the current roadmap, then select one actual business service for an end-to-end integration. Open decisions include the first provider, supported authentication, trusted read permissions, and downstream booking idempotency.
