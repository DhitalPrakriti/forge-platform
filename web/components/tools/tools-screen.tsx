"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Wrench, Plus, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api/forge";
import type { Tool, ToolName } from "@/lib/api/types";
import { DEMO_TOOLS } from "@/lib/tool-demo";
import { useWorkspace } from "../layout/providers";
import { WorkspaceScreen } from "../workspace/workspace-screen";
import {
  Badge,
  Card,
  ErrorNotice,
  JsonDetails,
  Loading,
  PageHeading,
} from "../ui/shared";
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
        eyebrow="PHASE 5 / TOOL HUB"
        title="Give agents permission to act."
        description="Register an installed demo tool, then select its exact revision when creating a new agent version."
      />
      <div className="notice">
        <ShieldCheck size={18} />
        <span>
          Local demo tools only. No external helpdesk, customer system, refund,
          or message is contacted.
        </span>
      </div>
      <ErrorNotice error={tools.error} retry={() => void tools.refetch()} />
      <ErrorNotice error={register.error || patch.error} />
      {tools.isPending && <Loading />}
      {tools.data && (
        <div className="tool-grid">
          {DEMO_TOOLS.map((demo) => {
            const tool = tools.data.find(
              (item) => item.name === demo.name && item.version === "1.0.0",
            );
            return (
              <Card key={demo.name} title={demo.label} subtitle={demo.name}>
                <div className="form-stack">
                  <Wrench size={23} />
                  <p className="muted">
                    {tool?.description || demo.description}
                  </p>
                  <div className="actions">
                    <Badge>{tool?.status || "NOT REGISTERED"}</Badge>
                    <span className="mono">v1.0.0</span>
                    {tool && <Badge>{tool.risk_level}</Badge>}
                  </div>
                  {tool ? (
                    <>
                      <p className="mono break-word">{tool.id}</p>
                      <dl className="definition-list">
                        <div>
                          <dt>Timeout</dt>
                          <dd>{tool.timeout_seconds}s</dd>
                        </div>
                        <div>
                          <dt>Idempotency</dt>
                          <dd>
                            {tool.idempotency_supported
                              ? "Supported"
                              : "Not supported"}
                          </dd>
                        </div>
                      </dl>
                      <Button
                        variant="outline"
                        disabled={patch.isPending}
                        onClick={() =>
                          tool.status === "ACTIVE"
                            ? setDisable(tool)
                            : patch.mutate({ id: tool.id, status: "ACTIVE" })
                        }
                      >
                        {tool.status === "ACTIVE"
                          ? `Disable ${demo.name}`
                          : `Enable ${demo.name}`}
                      </Button>
                      <JsonDetails
                        value={{
                          input: tool.input_schema,
                          output: tool.output_schema,
                        }}
                        label="Input / output schemas"
                      />
                    </>
                  ) : (
                    <Button
                      disabled={register.isPending}
                      onClick={() => register.mutate(demo.name)}
                    >
                      <Plus size={15} />
                      Register {demo.name}
                    </Button>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
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
            Registered policy: {policy.data.id}. Select it in your new agent
            version.
          </p>
        )}
      </Card>
      <ConfirmDialog
        open={!!disable}
        onOpenChange={(open) => {
          if (!open) setDisable(null);
        }}
        title={`Disable ${disable?.name}?`}
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
