"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/forge";
import type { MCPDiscoveredTool, Tool } from "@/lib/api/types";
import { Button } from "../ui/button";
import { Badge, Card, ErrorNotice, JsonDetails, Loading } from "../ui/shared";

export function McpTools({ org, tools }: { org: string; tools: Tool[] }) {
  const [server, setServer] = useState("");
  const client = useQueryClient();
  const servers = useQuery({
    queryKey: [org, "mcp-servers"],
    queryFn: () => api.mcpServers(org),
  });
  const discovered = useQuery({
    queryKey: [org, "mcp-discovery", server],
    queryFn: () => api.discoverMcp(org, server),
    enabled: false,
  });
  const register = useMutation({
    mutationFn: (tool: MCPDiscoveredTool) => api.registerMcp(org, server, tool),
    onSuccess: () =>
      void client.invalidateQueries({ queryKey: [org, "tools"] }),
  });
  const patch = useMutation({
    mutationFn: (tool: Tool) =>
      api.patchTool(
        org,
        tool.id,
        tool.status === "ACTIVE" ? "INACTIVE" : "ACTIVE",
      ),
    onSuccess: () =>
      void client.invalidateQueries({ queryKey: [org, "tools"] }),
  });
  return (
    <Card
      title="Connect tools with MCP"
      subtitle="Discover tools, review what they do, then add selected revisions to your agent."
    >
      <div className="form-stack">
        <p className="muted">
          Choose a server configured by your local operator. Credentials stay on
          the backend. Every external call asks for approval in the run page.
        </p>
        <ErrorNotice
          error={
            servers.error || discovered.error || register.error || patch.error
          }
        />
        {servers.isPending && <Loading />}
        {servers.data?.length === 0 && (
          <p className="inset-note">
            No MCP servers configured yet. Set FORGE_MCP_SERVERS on the API and
            worker using the MCP setup guide in docs/MCP_SESSION.md, then
            restart them.
          </p>
        )}
        <label htmlFor="mcp-server">MCP server</label>
        <select
          id="mcp-server"
          value={server}
          onChange={(e) => {
            setServer(e.target.value);
            register.reset();
          }}
          disabled={register.isPending || discovered.isFetching}
        >
          <option value="">Choose a server</option>
          {servers.data?.map((item) => (
            <option key={item.name} value={item.name}>
              {item.name}
            </option>
          ))}
        </select>
        <Button
          disabled={!server || discovered.isFetching}
          onClick={() => void discovered.refetch()}
        >
          {discovered.isFetching ? "Discovering…" : "Discover tools"}
        </Button>
        {discovered.data?.length === 0 && (
          <p>No tools advertised by this server.</p>
        )}
        {discovered.data?.map((item) => (
          <div className="inset-note" key={item.tool.name}>
            <strong>{item.tool.name}</strong>
            <p>{item.tool.description}</p>
            <Badge>APPROVAL REQUIRED</Badge>
            <JsonDetails
              label="Review input and output schemas"
              value={item.tool}
            />
            <Button
              disabled={register.isPending}
              onClick={() => register.mutate(item)}
            >
              Register {item.tool.name}
            </Button>
          </div>
        ))}
        {register.data && (
          <p role="status">
            Registered {register.data.name}. Clone your agent version and select
            this tool under tool permissions.
          </p>
        )}
        {tools
          .filter((t) => t.handler_type === "MCP_HTTP_V1")
          .map((tool) => (
            <div className="inset-note" key={tool.id}>
              <strong className="break-word">{tool.name}</strong>
              <p>{tool.description}</p>
              <Badge>{tool.status}</Badge>
              <Badge>APPROVAL REQUIRED</Badge>
              <JsonDetails label="Registered revision" value={tool} />
              <Button
                variant="outline"
                disabled={patch.isPending}
                onClick={() => patch.mutate(tool)}
              >
                {tool.status === "ACTIVE" ? "Disable" : "Enable"} {tool.name}
              </Button>
            </div>
          ))}
      </div>
    </Card>
  );
}
