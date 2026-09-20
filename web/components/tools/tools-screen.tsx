"use client";
import { toolPresentation } from "@/lib/tool-presentation";
import { ToolCatalog } from "./tool-catalog";
import { McpTools } from "./mcp-tools";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api/forge";
import type { Tool, ToolName } from "@/lib/api/types";
import { DEMO_TOOLS } from "@/lib/tool-demo";
import { useWorkspace } from "../layout/providers";
import { WorkspaceScreen } from "../workspace/workspace-screen";
import { Card, ErrorNotice, Loading, PageHeading } from "../ui/shared";
import { Button } from "../ui/button";
import { ConfirmDialog } from "../ui/confirm-dialog";
export function ToolsScreen() {
  const { workspace } = useWorkspace();
  const client = useQueryClient();
  const [disable, setDisable] = useState<Tool | null>(null);
  const tools = useQuery({
    queryKey: [workspace?.id, "tools"],
    queryFn: () => api.tools(workspace!.id),
    enabled: !!workspace,
  });
  const register = useMutation({
    mutationFn: (name: ToolName) => api.registerTool(workspace!.id, name),
    onSuccess: () =>
      void client.invalidateQueries({ queryKey: [workspace!.id, "tools"] }),
  });
  const policy = useMutation({
    mutationFn: () => api.registerPolicy(workspace!.id),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: [workspace!.id, "policies"] });
    },
  });
  const patch = useMutation({
    mutationFn: ({ id, status }: { id: string; status: Tool["status"] }) =>
      api.patchTool(workspace!.id, id, status),
    onSuccess: () => {
      setDisable(null);
      void client.invalidateQueries({ queryKey: [workspace!.id, "tools"] });
    },
    onError: () => setDisable(null),
  });
  if (!workspace) return <WorkspaceScreen />;
  return (
    <>
      <PageHeading
        eyebrow="WORKSPACE / TOOL HUB"
        title="Tools & capabilities"
        description="Register an installed tool, then select its exact revision when creating a new agent version."
      />
      <div className="notice">
        <ShieldCheck size={18} />
        <span>
          Built-in tools run locally. Connected MCP tools contact an external
          server and require your approval before each call.
        </span>
      </div>
      <ErrorNotice error={tools.error} retry={() => void tools.refetch()} />
      <ErrorNotice error={register.error || patch.error} />
      {tools.isPending && <Loading />}
      {tools.data && (
        <ToolCatalog
          tools={tools.data}
          action={(tool) => (
            <Button
              variant="outline"
              disabled={patch.isPending}
              aria-label={`${tool.status === "ACTIVE" ? "Disable" : "Enable"} ${tool.name}`}
              onClick={() =>
                tool.status === "ACTIVE"
                  ? setDisable(tool)
                  : patch.mutate({ id: tool.id, status: "ACTIVE" })
              }
            >
              {tool.status === "ACTIVE"
                ? `Disable ${toolPresentation(tool).title}`
                : `Enable ${toolPresentation(tool).title}`}
            </Button>
          )}
        />
      )}
      <details className="catalog-install">
        <summary>Connect an MCP server</summary>
        <McpTools
          key={workspace.id}
          org={workspace.id}
          tools={tools.data || []}
        />
      </details>
      <details className="catalog-install">
        <summary>Add built-in capabilities</summary>
        <p className="muted">
          Register only what your agent needs. Customer-service tools use demo
          data.
        </p>
        <div className="capability-grid">
          {DEMO_TOOLS.filter(
            (demo) =>
              !tools.data?.some(
                (t) => t.name === demo.name && t.version === "1.0.0",
              ),
          ).map((demo) => (
            <article className="capability-card" key={demo.name}>
              <h3>{demo.label}</h3>
              <p>{demo.description}</p>
              <Button
                disabled={register.isPending}
                onClick={() => register.mutate(demo.name)}
              >
                <Plus size={15} />
                Register {demo.name}
              </Button>
            </article>
          ))}
        </div>
      </details>
      <Card
        title="How a tool call works"
        subtitle="The model requests a function. FORGE decides whether it may run."
      >
        <p className="muted">
          Schema validation → exact version permission → local demo policy →
          limits → execute → output validation → persisted result. Only then
          does the result return to the model.
        </p>
        <p className="inset-note">
          Existing versions stay immutable. Clone an agent version to add tool
          permissions. Refund versions also need the installed refund policy
          below.
        </p>
      </Card>
      <details className="catalog-install">
        <summary>Customer-service demo policy</summary>
        <Card
          title="Refund policy v1.0.0"
          subtitle="USD amounts up to 100 allow; above 100 through 500 require approval; above 500 deny."
        >
          <Button disabled={policy.isPending} onClick={() => policy.mutate()}>
            Register refund policy
          </Button>
          <ErrorNotice error={policy.error} />
          {policy.data && (
            <p role="status" className="mono break-word">
              Refund policy registered. Select it in your new agent version.
            </p>
          )}
        </Card>
      </details>
      <ConfirmDialog
        open={!!disable}
        onOpenChange={(open) => {
          if (!open) setDisable(null);
        }}
        title={`Disable ${disable ? toolPresentation(disable).title : "tool"}?`}
        description="This blocks new executions of this tool across every version in this workspace. Calls already authorized may finish. You can enable it again later."
        confirmLabel="Disable tool"
        cancelLabel="Keep enabled"
        pending={patch.isPending}
        onConfirm={() =>
          disable && patch.mutate({ id: disable.id, status: "INACTIVE" })
        }
      />
    </>
  );
}
