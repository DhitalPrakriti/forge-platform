"use client";
import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArrowLeft, Copy, LockKeyhole, Play } from "lucide-react";
import { api } from "@/lib/api/forge";
import { date } from "@/lib/utils";
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
import { VersionForm } from "./version-form";
export function CreateVersionScreen({
  agentId,
  sourceId,
}: {
  agentId: string;
  sourceId?: string;
}) {
  const { workspace } = useWorkspace();
  const agent = useQuery({
    queryKey: [workspace?.id, "agent", agentId],
    queryFn: () => api.agent(workspace!.id, agentId),
    enabled: !!workspace,
  });
  const source = useQuery({
    queryKey: [workspace?.id, "version", agentId, sourceId],
    queryFn: () => api.version(workspace!.id, agentId, sourceId!),
    enabled: !!workspace && !!sourceId,
  });
  if (!workspace) return <WorkspaceScreen />;
  return (
    <>
      <Link href={`/agents/${agentId}`} className="back-link">
        <ArrowLeft size={15} />
        Back to agent
      </Link>
      <PageHeading
        eyebrow="STEP 2 / CONFIGURATION"
        title={sourceId ? "Clone into a new version" : "Create a version"}
        description={
          agent.data
            ? `Define how ${agent.data.name} behaves. Existing versions stay unchanged.`
            : "Load your agent’s configuration."
        }
      />
      <ErrorNotice
        error={agent.error || source.error}
        retry={() => {
          void agent.refetch();
          if (sourceId) void source.refetch();
        }}
      />
      {(agent.isPending || (sourceId && source.isPending)) && <Loading />}
      {agent.data && (!sourceId || source.data) && (
        <div className="form-layout">
          <VersionForm
            key={source.data?.id || "new"}
            org={workspace.id}
            agentId={agentId}
            source={source.data}
          />
          <div className="aside-note">
            <LockKeyhole size={24} />
            <h2>A record you can trust.</h2>
            <p>
              A version is a snapshot. Once saved, its instructions and
              configuration cannot be edited.
            </p>
            <p>
              To try a change, clone the version and give it a new label. Runs
              always refer to the exact version they used.
            </p>
          </div>
        </div>
      )}
    </>
  );
}
export function VersionDetailScreen({
  agentId,
  versionId,
}: {
  agentId: string;
  versionId: string;
}) {
  const { workspace } = useWorkspace();
  const client = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const version = useQuery({
    queryKey: [workspace?.id, "version", agentId, versionId],
    queryFn: () => api.version(workspace!.id, agentId, versionId),
    enabled: !!workspace,
  });
  const archive = useMutation({
    mutationFn: () => api.archive(workspace!.id, versionId),
    onSuccess: (updated) => {
      client.setQueryData(
        [workspace!.id, "version", agentId, versionId],
        updated,
      );
      void client.invalidateQueries({
        queryKey: [workspace!.id, "versions", agentId],
      });
      setConfirm(false);
    },
    onError: () => setConfirm(false),
  });
  if (!workspace) return <WorkspaceScreen />;
  const value = version.data;
  return (
    <>
      <Link href={`/agents/${agentId}`} className="back-link">
        <ArrowLeft size={15} />
        Back to agent
      </Link>
      <ErrorNotice error={version.error} retry={() => void version.refetch()} />
      {version.isPending && <Loading />}
      {value && (
        <>
          <PageHeading
            eyebrow="IMMUTABLE VERSION"
            title={value.version}
            description="A saved configuration. Changes belong in a new version."
            action={
              <div className="actions">
                <Button asChild variant="outline">
                  <Link
                    href={`/agents/${agentId}/versions/new?from=${versionId}`}
                  >
                    <Copy size={15} />
                    Clone version
                  </Link>
                </Button>
                {["DRAFT", "STAGING"].includes(value.lifecycle_status) && (
                  <Button asChild>
                    <Link
                      href={`/agents/${agentId}/versions/${versionId}/playground`}
                    >
                      <Play size={15} />
                      Test version
                    </Link>
                  </Button>
                )}
              </div>
            }
          />
          <div className="metadata-strip">
            <Badge>{value.lifecycle_status}</Badge>
            <span className="mono break-word">{value.id}</span>
            <span className="muted">Created {date(value.created_at)}</span>
          </div>
          <ErrorNotice error={archive.error} />
          <div className="two-column">
            <Card title="Instructions">
              <h3>Goal</h3>
              <p className="preserve">{value.goal}</p>
              <h3>System instructions</h3>
              <p className="preserve">{value.instructions}</p>
            </Card>
            <Card title="Configuration">
              <dl className="definition-list">
                <div>
                  <dt>Primary model</dt>
                  <dd className="mono">{value.primary_model}</dd>
                </div>
                <div>
                  <dt>Runtime template</dt>
                  <dd className="mono">{value.runtime_template_revision}</dd>
                </div>
                <div>
                  <dt>Maximum steps</dt>
                  <dd>{value.runtime_config.max_steps}</dd>
                </div>
                <div>
                  <dt>Maximum runtime</dt>
                  <dd>{value.runtime_config.max_runtime_seconds}s</dd>
                </div>
                <div>
                  <dt>Saved budget</dt>
                  <dd>${value.budget_config.max_cost_per_run_usd}</dd>
                </div>
                <div>
                  <dt>Tool bindings</dt>
                  <dd>{value.tool_version_ids.length}</dd>
                </div>
                <div>
                  <dt>Policy bindings</dt>
                  <dd>{value.policy_version_ids.length}</dd>
                </div>
              </dl>
              <p className="inset-note">
                Demo tool execution is available for permitted revisions. Budget
                enforcement and staging remain deferred.
              </p>
            </Card>
          </div>
          <Card title="Version record">
            <JsonDetails value={value} />
            {["DRAFT", "STAGING", "APPROVED", "DEPRECATED"].includes(
              value.lifecycle_status,
            ) && (
              <div className="archive-row">
                <div>
                  <strong>Archive this version</strong>
                  <p className="muted">
                    Keep the record while preventing new test runs.
                  </p>
                </div>
                <Button variant="outline" onClick={() => setConfirm(true)}>
                  <Archive size={15} />
                  Archive
                </Button>
              </div>
            )}
          </Card>
          <ConfirmDialog
            open={confirm}
            onOpenChange={setConfirm}
            title={`Archive ${value.version}?`}
            description="This version remains in the registry, but you will no longer be able to run it. There is no unarchive action in the current backend."
            pending={archive.isPending}
            onConfirm={() => archive.mutate()}
          />
        </>
      )}
    </>
  );
}
