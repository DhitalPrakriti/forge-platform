import { test, expect, type Page } from "@playwright/test";

// Integration tests require the migrated local/test backend using FORGE_MODEL_BACKEND=fake.
// Each test creates its own organization. Existing user data is never deleted or changed.
async function workspace(page: Page, label = "Browser test") {
  await page.goto("/workspace");
  await page.getByLabel("Workspace name").fill(label);
  await page.getByLabel("Workspace slug").fill(`ui-e2e-${crypto.randomUUID()}`);
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  await expect(page).toHaveURL(/\/agents$/);
}
async function version(page: Page) {
  await page.goto("/agents/new");
  await page.getByLabel("Agent name").fill("Review assistant");
  await page.getByLabel("Agent slug").fill("review-assistant");
  await page
    .getByLabel("Description (optional)")
    .fill("A local browser test agent.");
  await page
    .getByRole("button", { name: "Create agent & add version" })
    .click();
  await expect(page).toHaveURL(/\/versions\/new$/);
  await page.getByLabel("Version label").fill("v1");
  await page.getByLabel("Goal", { exact: true }).fill("Explain code simply.");
  await page
    .getByLabel("Instructions", { exact: true })
    .fill("Answer with a concise explanation.");
  await page.getByLabel("Model identifier").fill("browser-fake-model");
  await page.getByRole("button", { name: "Save immutable version" }).click();
  await expect(page.getByRole("link", { name: "Test version" })).toBeVisible();
  return page.url();
}
test("create, run, inspect, clone, archive, and switch workspaces", async ({
  page,
  request,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await workspace(page, "Review workspace");
  const versionUrl = await version(page);
  await page.getByRole("link", { name: "Test version" }).click();
  await page
    .getByLabel("Message", { exact: true })
    .fill("Hello from the console — explain function calling.");
  await page.getByRole("button", { name: "Run agent", exact: true }).click();
  await expect(page).toHaveURL(/\/runs\/[0-9a-f-]+$/);
  await expect(page.getByText("FAKE MODEL", { exact: true })).toBeVisible();
  await expect(
    page.getByText(
      "[FAKE MODEL — no provider call] Hello from the console — explain function calling.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Event timeline" }),
  ).toBeVisible();
  await expect(page.locator(".timeline")).toContainText("COMPLETED");
  await expect(page.getByText("forge-fake-v1", { exact: true })).toBeVisible();
  const runUrl = page.url();
  const runId = runUrl.split("/").at(-1)!;
  await page.screenshot({
    path: testInfo.outputPath("run-inspector-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("button", { name: "Refresh", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("run-inspector-mobile.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1050 });
  await page.goto("/runs");
  await expect(
    page.getByRole("link", { name: runId.slice(0, 8) }),
  ).toBeVisible();
  await page.goto(versionUrl);
  await page.getByRole("link", { name: "Clone version" }).click();
  await expect(page.getByLabel("Instructions", { exact: true })).toHaveValue(
    "Answer with a concise explanation.",
  );
  await page.getByLabel("Version label").fill("v2");
  await page.getByRole("button", { name: "Save immutable version" }).click();
  await expect(
    page.getByRole("heading", { name: "v2", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Archive", exact: true }).click();
  await expect(page.getByRole("alertdialog")).toBeVisible();
  await page.getByRole("button", { name: "Keep version" }).click();
  await expect(page.getByText("DRAFT", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Archive", exact: true }).click();
  await page
    .getByRole("button", { name: "Archive version", exact: true })
    .click();
  await expect(page.getByText("ARCHIVED", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Test version" })).toHaveCount(0);
  await workspace(page, "Other workspace");
  await expect(page.getByText("Your next agent starts here.")).toBeVisible();
  await page.goto("/runs");
  await expect(page.getByText("No runs opened yet")).toBeVisible();
  await page.goto(runUrl);
  await expect(page.locator(".error-notice")).toContainText("not found");
  const selected = await page.getByLabel("Active workspace").inputValue();
  const forbidden = await request.get(
    `http://127.0.0.1:8000/api/v1/runs/${runId}`,
    { headers: { "X-Organization-ID": selected } },
  );
  expect(forbidden.status()).toBe(404);
  await page
    .getByLabel("Active workspace")
    .selectOption({ label: "Review workspace" });
  await expect(page.getByText("Your agents, from the inside.")).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("overview-desktop.png"),
    fullPage: true,
  });
  const originalWorkspace = await page
    .getByLabel("Active workspace")
    .inputValue();
  await page.reload();
  await expect(page.getByLabel("Active workspace")).toHaveValue(
    originalWorkspace,
  );
  expect(errors).toEqual([]);
});

test("retry after a lost response retrieves the same persisted run", async ({
  page,
}) => {
  await workspace(page);
  await version(page);
  await page.getByRole("link", { name: "Test version" }).click();
  const keys: string[] = [];
  const runIds: string[] = [];
  await page.route("**/api/forge/runs", async (route) => {
    keys.push(route.request().headers()["idempotency-key"]);
    const response = await route.fetch();
    const body = await response.json();
    runIds.push(body.id);
    if (keys.length === 1) await route.abort("failed");
    else await route.fulfill({ response });
  });
  await page
    .getByLabel("Message", { exact: true })
    .fill("Retry should not duplicate this run.");
  await page.getByRole("button", { name: "Run agent", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Retry same request" }),
  ).toBeVisible();
  await expect(page.getByLabel("Message", { exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Retry same request" }).click();
  await expect(page).toHaveURL(/\/runs\/[0-9a-f-]+$/);
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBeTruthy();
  expect(keys[0]).toBe(keys[1]);
  expect(runIds[0]).toBeTruthy();
  expect(runIds[0]).toBe(runIds[1]);
});

test("workspace validation and duplicate agent errors are visible", async ({
  page,
}) => {
  await page.goto("/workspace");
  await page
    .getByLabel("Organization ID", { exact: true })
    .fill("X-Organization-ID");
  await page.getByRole("button", { name: "Connect workspace" }).click();
  await expect(
    page.getByText("Enter a valid organization UUID."),
  ).toBeVisible();
  await workspace(page);
  await version(page);
  await page.goto("/agents/new");
  await page.getByLabel("Agent name").fill("Duplicate");
  await page.getByLabel("Agent slug").fill("review-assistant");
  await page
    .getByRole("button", { name: "Create agent & add version" })
    .click();
  await expect(page.locator(".error-notice")).toContainText("Trace:");
  await expect(page).toHaveURL(/\/agents\/new$/);
});

test("active runs poll to failure and unknown cost stays unavailable", async ({
  page,
}) => {
  await workspace(page);
  const org = await page.getByLabel("Active workspace").inputValue();
  const runId = crypto.randomUUID();
  const now = new Date().toISOString();
  let reads = 0;
  // Isolated transport fixtures exercise error/polling presentation, not provider execution.
  await page.route(`**/api/forge/runs/${runId}`, async (route) => {
    reads += 1;
    const done = reads > 1;
    await route.fulfill({
      json: {
        id: runId,
        organization_id: org,
        agent_id: crypto.randomUUID(),
        agent_version_id: crypto.randomUUID(),
        status: done ? "FAILED" : "RUNNING",
        state_version: done ? 2 : 1,
        input: { message: "An example failing run" },
        output: null,
        error_code: done ? "MODEL_PROVIDER_ERROR" : null,
        current_step: 1,
        model_calls_count: 1,
        tool_calls_count: 0,
        total_cost: null,
        runtime_build_version: "test-fixture",
        execution_config: {
          provider: "google",
          requested_model: "fixture-model",
        },
        started_at: now,
        completed_at: done ? now : null,
        created_at: now,
        updated_at: now,
      },
    });
  });
  await page.route(`**/api/forge/runs/${runId}/events?*`, (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route(`**/api/forge/runs/${runId}/model-calls`, (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route(`**/api/forge/runs/${runId}/tool-calls?*`, (route) =>
    route.fulfill({ json: [] }),
  );
  await page.goto(`/runs/${runId}`);
  await expect(
    page.getByText("Run is active. Refreshing saved evidence every 2 seconds…"),
  ).toBeVisible();
  await expect(page.locator(".error-notice")).toContainText(
    "MODEL_PROVIDER_ERROR",
    { timeout: 7000 },
  );
  await expect(page.getByText("No output was recorded.")).toBeVisible();
  await expect(page.locator(".cost-value")).toHaveText("Not available");
  expect(reads).toBeGreaterThanOrEqual(2);
});

test("register tools, clone permissions, create a demo ticket, and inspect the call", async ({
  page,
}, testInfo) => {
  await workspace(page, "Tool review workspace");
  await page.goto("/tools");
  for (const name of [
    "lookup_customer",
    "lookup_transactions",
    "create_ticket",
  ]) {
    await page
      .getByRole("button", { name: `Register ${name}`, exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: `Disable ${name}`, exact: true }),
    ).toBeVisible();
  }
  await page.screenshot({
    path: testInfo.outputPath("tool-hub.png"),
    fullPage: true,
  });
  const original = await version(page);
  await page.getByRole("link", { name: "Clone version" }).click();
  await page.getByLabel("Version label").fill("v2-tools");
  for (const name of [
    "lookup_customer",
    "lookup_transactions",
    "create_ticket",
  ]) {
    await page.getByRole("checkbox", { name: new RegExp(name) }).check();
  }
  await page.getByRole("button", { name: "Save immutable version" }).click();
  await expect(
    page.getByRole("heading", { name: "v2-tools", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Test version" }).click();
  await page.getByText("Fake-backend tool examples", { exact: true }).click();
  await page
    .getByRole("button", { name: "Create demo ticket", exact: true })
    .click();
  await expect(page.getByLabel("Message", { exact: true })).toHaveValue(
    /\/tool create_ticket/,
  );
  const completed = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/forge/runs") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Run agent", exact: true }).click();
  const run = await (await completed).json();
  expect(run.status).toBe("QUEUED");
  await expect(page).toHaveURL(new RegExp(`/runs/${run.id}$`));
  await expect(page.locator(".metadata-strip")).toContainText("COMPLETED");
  const finalRun = await (
    await page.request.get(`/api/forge/runs/${run.id}`, {
      headers: { "X-Organization-ID": run.organization_id },
    })
  ).json();
  expect(finalRun.model_calls_count).toBe(2);
  expect(finalRun.tool_calls_count).toBe(1);
  const call = page.locator(".tool-call");
  await expect(call).toContainText("create_ticket");
  await expect(call).toContainText("ALLOW");
  await expect(call).toContainText('"ticket_id"');
  await expect(call).toContainText('"demo": true');
  await page.screenshot({
    path: testInfo.outputPath("tool-run-inspector.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.goto(original);
  await page.getByRole("link", { name: "Test version" }).click();
  await page
    .getByLabel("Message", { exact: true })
    .fill('/tool lookup_customer {"customer_id":"cust_001"}');
  await page.getByRole("button", { name: "Run agent", exact: true }).click();
  await expect(page.locator(".tool-call")).toContainText("TOOL_NOT_ALLOWED");
  await page.goto("/tools");
  await page
    .getByRole("button", { name: "Disable create_ticket", exact: true })
    .click();
  await expect(page.getByRole("alertdialog")).toBeVisible();
  await page.getByRole("button", { name: "Disable tool", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Enable create_ticket", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Enable create_ticket", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Disable create_ticket", exact: true }),
  ).toBeVisible();
});

test("refund policy, human approval, and automatic worker continuation", async ({
  page,
}, testInfo) => {
  const token = process.env.FORGE_APPROVAL_REVIEWER_TOKEN;
  test.skip(
    !token,
    "Configure the local API reviewer token for this approval integration test.",
  );
  await workspace(page, "Refund review");
  const initial = await version(page);
  await page.goto("/tools");
  await page
    .getByRole("button", { name: "Register issue_refund", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Disable issue_refund", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Register refund policy", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("Registered policy");
  await page.goto(initial);
  await page.getByRole("link", { name: "Clone version" }).click();
  await page.getByLabel("Version label").fill("v2-refunds");
  await page.getByRole("checkbox", { name: /issue_refund/ }).check();
  await page.getByRole("checkbox", { name: /demo-refund/ }).check();
  await page.getByRole("button", { name: "Save immutable version" }).click();
  await page.getByRole("link", { name: "Test version" }).click();
  await page
    .getByLabel("Message", { exact: true })
    .fill(
      '/tool issue_refund {"customer_id":"cust_001","amount_usd":"425.00"}',
    );
  await page.getByRole("button", { name: "Run agent", exact: true }).click();
  await expect(page).toHaveURL(/\/runs\/[0-9a-f-]+$/);
  await expect(
    page.getByRole("heading", { name: "Refund approvals" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Simulated USD 425.00 refund to cust_001",
    }),
  ).toBeVisible();
  await page.getByLabel("Local reviewer credential").fill(token!);
  await page
    .getByLabel("Decision reason")
    .fill("Reviewed exact demo amount and customer.");
  await page
    .getByRole("button", { name: "Approve refund", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Save decision", exact: true })
    .click();
  // A saved decision dispatches the queued run without a separate resume request.
  await page.reload();
  await expect(page.locator(".metadata-strip")).toContainText("COMPLETED");
  await expect(
    page.getByText("SIMULATED", { exact: false }).first(),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("refund-completed-mobile.png"),
    fullPage: true,
  });
});

test("retry a failed queued run creates a linked run", async ({ page }) => {
  await workspace(page);
  await version(page);
  await page.getByRole("link", { name: "Test version" }).click();
  await page
    .getByLabel("Message", { exact: true })
    .fill('/tool lookup_customer {"customer_id":"cust_001"}');
  await page.getByRole("button", { name: "Run agent", exact: true }).click();
  await expect(page.locator(".metadata-strip")).toContainText("FAILED");
  const original = page.url().split("/").at(-1)!;
  const response = page.waitForResponse((r) =>
    r.url().endsWith(`/runs/${original}/retry`),
  );
  await page
    .getByRole("button", { name: "Retry as new run", exact: true })
    .click();
  const retry = await (await response).json();
  expect(retry.retry_of_run_id).toBe(original);
  expect(retry.id).not.toBe(original);
  await expect(page).toHaveURL(new RegExp(`/runs/${retry.id}$`));
});

test("cancel control confirms and polls worker completion", async ({
  page,
}) => {
  await workspace(page);
  const org = await page.getByLabel("Active workspace").inputValue();
  const runId = crypto.randomUUID();
  const now = new Date().toISOString();
  let cancelled = false;
  const fixture = () => ({
    id: runId,
    organization_id: org,
    agent_id: crypto.randomUUID(),
    agent_version_id: crypto.randomUUID(),
    status: cancelled ? "CANCELLED" : "QUEUED",
    state_version: 1,
    input: { message: "Cancellation fixture" },
    output: null,
    error_code: cancelled ? "RUN_CANCELLED" : null,
    current_step: 0,
    model_calls_count: 0,
    tool_calls_count: 0,
    total_cost: null,
    runtime_build_version: "test-fixture",
    execution_config: { provider: "fake", execution_mode: "queued" },
    started_at: now,
    completed_at: cancelled ? now : null,
    created_at: now,
    updated_at: now,
  });
  await page.route(`**/api/forge/runs/${runId}`, (r) =>
    r.fulfill({ json: fixture() }),
  );
  for (const suffix of ["events?*", "model-calls", "tool-calls?*"])
    await page.route(`**/api/forge/runs/${runId}/${suffix}`, (r) =>
      r.fulfill({ json: [] }),
    );
  await page.route(`**/api/forge/runs/${runId}/cancel`, (r) => {
    cancelled = true;
    return r.fulfill({ status: 202, json: fixture() });
  });
  await page.goto(`/runs/${runId}`);
  await page.getByRole("button", { name: "Cancel run", exact: true }).click();
  await expect(page.getByRole("alertdialog")).toBeVisible();
  await page
    .getByRole("button", { name: "Request cancellation", exact: true })
    .click();
  await expect(page.locator(".metadata-strip")).toContainText("CANCELLED");
  await expect(
    page.getByRole("button", { name: "Cancel run", exact: true }),
  ).toHaveCount(0);
});
