import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, test, vi } from "vitest";
import { LatestRunLink } from "../components/runs/version-runs";
import { api } from "../lib/api/forge";

vi.mock("../lib/api/forge", () => ({ api: { versionRuns: vi.fn() } }));
test("latest run link opens the exact run without displaying message content", async () => {
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
      <LatestRunLink org="workspace-id" versionId="version-id" />
    </QueryClientProvider>,
  );
  expect(
    await screen.findByRole("link", { name: /View latest run/ }),
  ).toHaveAttribute("href", "/runs/12345678-abcd-4000-8000-123456789abc");
  expect(
    screen.queryByText("Review my Python function"),
  ).not.toBeInTheDocument();
  expect(api.versionRuns).toHaveBeenCalledWith(
    "workspace-id",
    "version-id",
    0,
    1,
  );
});
