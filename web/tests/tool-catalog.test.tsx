import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { ToolCatalog } from "../components/tools/tool-catalog";
import type { Tool } from "../lib/api/types";
const tools = [
  {
    id: "python",
    name: "inspect_python",
    version: "1.0.0",
    handler_type: "BUILTIN",
    status: "ACTIVE",
    description: "Inspect pasted Python",
  },
  {
    id: "mcp",
    name: "mcp_aa0328cc5594_inspect_code",
    version: "a".repeat(64),
    handler_type: "MCP_HTTP_V1",
    status: "ACTIVE",
    description: "Inspect code on a server",
  },
  {
    id: "refund",
    name: "issue_refund",
    version: "1.0.0",
    handler_type: "BUILTIN",
    status: "INACTIVE",
    description: "Simulated refund",
  },
] as Tool[];
function Selector() {
  const [selected, setSelected] = useState(["python"]);
  return (
    <ToolCatalog tools={tools} selected={selected} onSelect={setSelected} />
  );
}
test("filters by purpose and source without removing selected permissions", () => {
  render(<Selector />);
  fireEvent.change(screen.getByLabelText("Tool category"), {
    target: { value: "Code review" },
  });
  expect(
    screen.queryByRole("heading", { name: "Simulated refund" }),
  ).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Tool source"), {
    target: { value: "MCP server" },
  });
  expect(screen.getByRole("status")).toHaveTextContent(
    "1 tools shown · 1 selected",
  );
  fireEvent.click(screen.getByRole("checkbox", { name: /mcp_aa/ }));
  expect(screen.getByRole("status")).toHaveTextContent("2 selected");
  fireEvent.click(
    screen.getByRole("button", { name: "Remove Python code inspection" }),
  );
  expect(screen.getByRole("status")).toHaveTextContent("1 selected");
});
test("keeps full identities collapsed and blocks selection of inactive tools", () => {
  render(<Selector />);
  expect(screen.getByRole("checkbox", { name: /issue_refund/ })).toBeDisabled();
  const details = screen.getAllByText("Technical details");
  expect(details[0].closest("details")).not.toHaveAttribute("open");
  fireEvent.change(screen.getByLabelText("Search tools"), {
    target: { value: "nothing-matches" },
  });
  expect(screen.getByText(/No tools match/)).toBeVisible();
  expect(screen.getByRole("status")).toHaveTextContent("1 selected");
});
