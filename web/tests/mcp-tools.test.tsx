import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, test, vi } from "vitest";
import { McpTools } from "../components/tools/mcp-tools";
import { api } from "../lib/api/forge";
import type { Tool } from "../lib/api/types";

function show() {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <McpTools org="org" tools={[]} />
    </QueryClientProvider>,
  );
}

test("explains setup when no servers are configured", async () => {
  vi.spyOn(api, "mcpServers").mockResolvedValue([]);
  show();
  expect(
    await screen.findByText(/No MCP servers configured/),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Discover tools" })).toBeDisabled();
  vi.restoreAllMocks();
});

test("discovers and registers only the reviewed fingerprint", async () => {
  const item = {
    tool: {
      name: "inspect",
      description: "Inspect code",
      inputSchema: { type: "object" },
    },
    fingerprint: "reviewed-fingerprint",
  };
  vi.spyOn(api, "mcpServers").mockResolvedValue([{ name: "code" }]);
  vi.spyOn(api, "discoverMcp").mockResolvedValue([item]);
  const register = vi
    .spyOn(api, "registerMcp")
    .mockResolvedValue({ name: "mcp_inspect" } as Tool);
  show();
  await screen.findByRole("option", { name: "code" });
  fireEvent.change(screen.getByLabelText("MCP server"), {
    target: { value: "code" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Discover tools" }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Register inspect" }),
  );
  await waitFor(() =>
    expect(register).toHaveBeenCalledWith("org", "code", item),
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Clone your agent version",
  );
  vi.restoreAllMocks();
});
