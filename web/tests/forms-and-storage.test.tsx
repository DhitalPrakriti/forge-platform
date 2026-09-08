import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Providers } from "@/components/layout/providers";
import { WorkspaceScreen } from "@/components/workspace/workspace-screen";
import { organizationIdSchema, versionSchema } from "@/lib/schemas";
import { loadRunIds, loadWorkspaces, rememberRun } from "@/lib/storage";
import { cost } from "@/lib/utils";
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
describe("forms and local context", () => {
  it("explains an invalid workspace UUID before sending a request", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    render(
      <Providers>
        <WorkspaceScreen />
      </Providers>,
    );
    fireEvent.change(screen.getByLabelText("Organization ID"), {
      target: { value: "X-Organization-ID" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Connect workspace" }));
    expect(
      await screen.findByText("Enter a valid organization UUID."),
    ).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });
  it("shows required workspace fields without calling the server", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    render(
      <Providers>
        <WorkspaceScreen />
      </Providers>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Create workspace" }));
    await waitFor(() =>
      expect(screen.getByText("Enter a name.")).toBeVisible(),
    );
    expect(fetch).not.toHaveBeenCalled();
  });
  it("accepts UUID values and rejects the header name", () => {
    expect(
      organizationIdSchema.safeParse({ id: crypto.randomUUID() }).success,
    ).toBe(true);
    expect(
      organizationIdSchema.safeParse({ id: "X-Organization-ID" }).success,
    ).toBe(false);
  });
  it("rejects blank behavior, fractional steps, and over-precise budgets", () => {
    const valid = {
      tool_version_ids: [],
      version: "v1",
      goal: "Help",
      instructions: "Be useful",
      primary_model: "test-model",
      max_steps: 12,
      max_runtime_seconds: 180,
      max_cost_per_run_usd: "0.20",
    };
    expect(versionSchema.safeParse(valid).success).toBe(true);
    for (const change of [
      { goal: "  " },
      { max_steps: 1.5 },
      { max_cost_per_run_usd: "0.0000001" },
      { max_cost_per_run_usd: "0" },
    ])
      expect(versionSchema.safeParse({ ...valid, ...change }).success).toBe(
        false,
      );
  });
  it("keeps run history isolated by workspace and ignores corrupt storage", () => {
    const run = crypto.randomUUID();
    rememberRun("org-a", run);
    rememberRun("org-a", run);
    expect(loadRunIds("org-a")).toEqual([run]);
    expect(loadRunIds("org-b")).toEqual([]);
    localStorage.setItem("forge.workspaces.v1", "not json");
    expect(loadWorkspaces().selectedId).toBeNull();
    localStorage.setItem("forge.runs.v1.org-a", '["not-a-uuid"]');
    expect(loadRunIds("org-a")).toEqual([]);
  });
  it("distinguishes unavailable cost from a recorded zero", () => {
    expect(cost(null)).toBe("Not available");
    expect(cost("0.00000000")).toBe("$0.00000000");
  });
});
