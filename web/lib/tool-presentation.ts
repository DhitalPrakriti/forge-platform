import type { Tool } from "./api/types";
import { DEMO_TOOLS } from "./tool-demo";
export function toolPresentation(tool: Pick<Tool, "name" | "handler_type">) {
  const mcp = tool.handler_type === "MCP_HTTP_V1";
  const remote = tool.name.replace(/^mcp_[a-f0-9]{12}_/, "");
  const builtin = DEMO_TOOLS.find((item) => item.name === tool.name);
  const category =
    tool.name === "inspect_python" || (mcp && remote === "inspect_code")
      ? "Code review"
      : mcp
        ? "Connected capabilities"
        : "Customer service demos";
  return {
    title:
      builtin?.label ||
      remote.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase()),
    category,
    source: mcp ? "MCP server" : "Built-in",
    approval: mcp
      ? "Approval every call"
      : tool.name === "issue_refund"
        ? "Refund policy required"
        : "No human approval",
    guidance: mcp
      ? "Use when this server’s advertised capability is needed. Review the arguments before approving."
      : tool.name === "inspect_python"
        ? "Use for syntax and structure checks on pasted Python. Does not run code, inspect repositories, or prove correctness."
        : tool.name === "lookup_customer"
          ? "Use to retrieve a synthetic customer profile before answering account questions."
          : tool.name === "lookup_transactions"
            ? "Use to check synthetic transaction history before discussing a payment."
            : tool.name === "create_ticket"
              ? "Use when a demo support issue needs a locally saved ticket. Does not contact a helpdesk."
              : "Use only for simulated refund requests. No real money moves.",
  };
}
export function matchesTool(tool: Tool, query: string, category: string) {
  const info = toolPresentation(tool);
  return (
    (category === "All" || category === info.category) &&
    `${info.title} ${tool.name} ${tool.description}`
      .toLowerCase()
      .includes(query.toLowerCase())
  );
}
