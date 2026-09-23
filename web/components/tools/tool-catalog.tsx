"use client";
import { useState, type ReactNode } from "react";
import { Search, Wrench, Plug } from "lucide-react";
import type { Tool } from "@/lib/api/types";
import { matchesTool, toolPresentation } from "@/lib/tool-presentation";
import { Badge, JsonDetails } from "../ui/shared";

export function ToolCatalog({
  tools,
  selected,
  onSelect,
  action,
}: {
  tools: Tool[];
  selected?: string[];
  onSelect?: (ids: string[]) => void;
  action?: (tool: Tool) => ReactNode;
}) {
  const [source, setSource] = useState("All sources");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [onlySelected, setOnlySelected] = useState(false);
  const visible = tools
    .filter(
      (t) =>
        matchesTool(t, query, category) &&
        (source === "All sources" || toolPresentation(t).source === source) &&
        (!onlySelected || selected?.includes(t.id)),
    )
    .sort(
      (a, b) =>
        toolPresentation(a).title.localeCompare(toolPresentation(b).title) ||
        a.version.localeCompare(b.version),
    );
  return (
    <div className="capability-browser">
      <div className="capability-toolbar">
        <label className="capability-search">
          <Search size={17} />
          <span className="sr-only">Search tools</span>
          <input
            aria-label="Search tools"
            placeholder="Search by capability or tool name…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <label>
          <span className="sr-only">Tool category</span>
          <select
            aria-label="Tool category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            {[
              "All",
              "Code review",
              "Knowledge",
              "Customer service demos",
              "Connected capabilities",
            ].map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">Tool source</span>
          <select
            aria-label="Tool source"
            value={source}
            onChange={(e) => setSource(e.target.value)}
          >
            {["All sources", "Built-in", "MCP server"].map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="actions">
        <span className="muted" role="status">
          {visible.length} tools shown
          {selected ? ` · ${selected.length} selected` : ""}
        </span>
        {selected && (
          <label className="selection-toggle">
            <input
              type="checkbox"
              checked={onlySelected}
              onChange={(e) => setOnlySelected(e.target.checked)}
            />
            Selected only
          </label>
        )}
      </div>
      {selected && selected.length > 0 && (
        <div className="selected-capabilities" aria-label="Selected tools">
          {tools
            .filter((t) => selected.includes(t.id))
            .map((t) => (
              <button
                type="button"
                key={t.id}
                onClick={() => onSelect?.(selected.filter((id) => id !== t.id))}
                aria-label={`Remove ${toolPresentation(t).title}`}
              >
                {toolPresentation(t).title} · {toolPresentation(t).source} ×
              </button>
            ))}
        </div>
      )}
      <div className="capability-grid">
        {visible.map((tool) => {
          const info = toolPresentation(tool);
          const checked = selected?.includes(tool.id) || false;
          return (
            <article
              key={tool.id}
              className={`capability-card ${checked ? "is-selected" : ""}`}
            >
              <div className="capability-heading">
                <span className="capability-icon">
                  {info.source === "Built-in" ? (
                    <Wrench size={20} />
                  ) : (
                    <Plug size={20} />
                  )}
                </span>
                <div>
                  <h3>{info.title}</h3>
                  <span className="muted">
                    {info.source} · {info.category}
                  </span>
                </div>
                <Badge>{tool.status}</Badge>
              </div>
              <p>{tool.description}</p>
              <p className="capability-guidance">{info.guidance}</p>
              <div className="actions">
                <Badge>{info.approval}</Badge>
                <span className="muted">
                  {tool.handler_type === "MCP_HTTP_V1"
                    ? `Revision ${tool.version.slice(0, 8)}`
                    : `v${tool.version}`}
                </span>
              </div>
              {onSelect && selected && (
                <label className="capability-select">
                  <input
                    type="checkbox"
                    aria-label={`${info.title} (${tool.name})`}
                    checked={checked}
                    disabled={tool.status !== "ACTIVE" && !checked}
                    onChange={(e) =>
                      onSelect(
                        e.target.checked
                          ? [...selected, tool.id]
                          : selected.filter((id) => id !== tool.id),
                      )
                    }
                  />
                  {checked
                    ? "Allowed for this version"
                    : tool.status === "ACTIVE"
                      ? "Allow this tool"
                      : "Disabled in workspace"}
                </label>
              )}
              {action?.(tool)}
              <JsonDetails
                label="Technical details"
                value={{
                  tool_id: tool.id,
                  function_name: tool.name,
                  revision: tool.version,
                  handler: tool.handler_type,
                  risk: tool.risk_level,
                  timeout_seconds: tool.timeout_seconds,
                  retry_safe: tool.retry_safe,
                  idempotency_supported: tool.idempotency_supported,
                  input_schema: tool.input_schema,
                  output_schema: tool.output_schema,
                }}
              />
            </article>
          );
        })}
      </div>
      {!visible.length && (
        <p className="inset-note">
          No tools match these filters. Try another category or clear your
          search.
        </p>
      )}
      {selected && (
        <p className="inset-note">
          Choose tools for the agent’s job. Similar built-in and MCP tools may
          overlap; usually choose one. The model decides which allowed tool to
          request from its description and your instructions. FORGE validates
          permissions and arguments before execution.
        </p>
      )}
    </div>
  );
}
