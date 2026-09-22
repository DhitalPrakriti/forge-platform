import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, test, vi } from "vitest";
import { VersionRuns } from "../components/runs/version-runs";
import { api } from "../lib/api/forge";

vi.mock("../lib/api/forge", () => ({ api: { versionRuns: vi.fn() } }));
test("version history links to exact persisted run and identifies its input", async () => {
  vi.mocked(api.versionRuns).mockResolvedValue([
    {
      id: "12345678-abcd-4000-8000-123456789abc",
      status: "COMPLETED",
      created_at: "2026-09-22T12:00:00Z",
      input: { message: "Review my Python function" },
    } as Awaited<ReturnType<typeof api.versionRuns>>[number],
  ]);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <VersionRuns org="workspace-id" versionId="version-id" />
    </QueryClientProvider>,
  );
  expect(await screen.findByRole("link", { name: /Open run/ })).toHaveAttribute(
    "href",
    "/runs/12345678-abcd-4000-8000-123456789abc",
  );
  expect(screen.getByText("Review my Python function")).toBeVisible();
  expect(api.versionRuns).toHaveBeenCalledWith("workspace-id", "version-id", 0);
});
