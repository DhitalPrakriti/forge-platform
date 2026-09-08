"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { ArrowLeft, Check, Copy, ExternalLink, RefreshCw } from "lucide-react";
import { api } from "@/lib/api/forge";
import { rememberRun } from "@/lib/storage";
import { cost, date, shortId } from "@/lib/utils";
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
import { ToolCallInspector } from "../tools/tool-call-inspector";
import { Button } from "../ui/button";
const active = (status?: string) =>
  ["CREATED", "RUNNING", "WAITING_FOR_TOOL"].includes(status || "");
export function RunDetailScreen({ runId }: { runId: string }) {
  const { workspace } = useWorkspace();
  const client = useQueryClient();
  const [copyState, setCopyState] = useState("");
  const [storageWarning, setStorageWarning] = useState(false);
  const run = useQuery({
    queryKey: [workspace?.id, "run", runId],
    queryFn: () => api.run(workspace!.id, runId),
    enabled: !!workspace,
    refetchInterval: (query) =>
      active(query.state.data?.status) ? 2000 : false,
  });
  const events = useInfiniteQuery({
    queryKey: [workspace?.id, "events", runId],
    queryFn: ({ pageParam }) => api.events(workspace!.id, runId, pageParam),
    enabled: !!workspace && !!run.data,
    initialPageParam: -1,
    getNextPageParam: (last) =>
      last.length === 100 ? last[last.length - 1].sequence_number : undefined,
    refetchInterval: active(run.data?.status) ? 2000 : false,
  });
  const calls = useQuery({
    queryKey: [workspace?.id, "model-calls", runId],
    queryFn: () => api.modelCalls(workspace!.id, runId),
    enabled: !!workspace && !!run.data,
    refetchInterval: active(run.data?.status) ? 2000 : false,
  });
  const orgId = workspace?.id;
  const status = run.data?.status;
  useEffect(() => {
    if (orgId && status) {
      setStorageWarning(!rememberRun(orgId, runId)); // eslint-disable-line react-hooks/set-state-in-effect
      void client.invalidateQueries({ queryKey: [orgId, "events", runId] });
      void client.invalidateQueries({ queryKey: [orgId, "tool-calls", runId] });
      void client.invalidateQueries({
        queryKey: [orgId, "model-calls", runId],
      });
    }
  }, [orgId, runId, status, client]);
  if (!workspace) return <WorkspaceScreen />;
  const value = run.data;
  return (
    <>
      <Link href="/runs" className="back-link">
        <ArrowLeft size={15} />
        Run history
      </Link>
      <ErrorNotice error={run.error} retry={() => void run.refetch()} />
      {run.isPending && <Loading />}
      {value && (
        <>
          <PageHeading
            eyebrow="RUN INSPECTOR"
            title={`Run ${shortId(runId)}`}
            description="Saved execution evidence, from request to result."
            action={
              <Button
                variant="outline"
                onClick={() => {
                  void run.refetch();
                  void events.refetch();
                  void calls.refetch();
                  void client.invalidateQueries({
                    queryKey: [workspace.id, "tool-calls", runId],
                  });
                }}
              >
                <RefreshCw size={15} />
                Refresh
              </Button>
            }
          />
          <div className="metadata-strip">
            <Badge>{value.status}</Badge>
            <Badge>{value.execution_config.provider || "UNKNOWN"}</Badge>
            <span className="mono break-word">{runId}</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(runId);
                  setCopyState("Copied");
                } catch {
                  setCopyState("Select the ID above to copy it.");
                }
              }}
              aria-label="Copy run ID"
            >
              {copyState === "Copied" ? (
                <Check size={14} />
              ) : (
                <Copy size={14} />
              )}
            </Button>
            <span role="status" className="muted">
              {copyState}
            </span>
          </div>
          {storageWarning && (
            <p className="notice">
              Browser storage is unavailable. Save this run ID to open it later.
            </p>
          )}
          {value.execution_config.provider === "fake" && (
            <div className="notice">
              <strong>FAKE MODEL</strong>
              <span>
                This run tested the application flow. No AI provider was called;
                token counts are simulated.
              </span>
            </div>
          )}
          {value.error_code && (
            <div role="alert" className="error-notice">
              <div>
                <strong>
                  Run {value.status.toLowerCase().replaceAll("_", " ")}
                </strong>
                <p className="mono">{value.error_code}</p>
                <p>
                  Inspect the model-call record below for the saved failure
                  type.
                </p>
              </div>
            </div>
          )}
          {active(value.status) && (
            <Loading label="Run is active. Refreshing saved evidence every 2 seconds…" />
          )}
          <div className="summary-grid">
            <Card>
              <div className="metric-label">Model calls</div>
              <div className="metric-value">{value.model_calls_count}</div>
              <p className="muted">{value.tool_calls_count} tool calls</p>
            </Card>
            <Card>
              <div className="metric-label">Recorded cost</div>
              <div className="metric-value cost-value">
                {cost(value.total_cost)}
              </div>
              <p className="muted">Unknown cost is not counted as zero</p>
            </Card>
            <Card>
              <div className="metric-label">Version</div>
              <Link
                className="metric-value text-link"
                href={`/agents/${value.agent_id}/versions/${value.agent_version_id}`}
              >
                {shortId(value.agent_version_id)}
                <ExternalLink size={15} />
              </Link>
              <p className="muted">Exact configuration used</p>
            </Card>
          </div>
          <div className="two-column">
            <Card title="Input" subtitle="The message sent for this run.">
              <p className="preserve output-text">{value.input.message}</p>
            </Card>
            <Card
              title="Output"
              subtitle="The saved response from the backend."
            >
              <p className="preserve output-text">
                {value.output?.message ??
                  (active(value.status)
                    ? "Waiting for a result…"
                    : "No output was recorded.")}
              </p>
            </Card>
          </div>
          <div className="inspector-grid">
            <Card
              title="Event timeline"
              subtitle="Persisted events in sequence order."
            >
              <ErrorNotice
                error={events.error}
                retry={() => void events.refetch()}
              />
              {events.isPending && <Loading />}
              {events.data && !events.data.pages.flat().length && (
                <p className="muted">No events have been recorded yet.</p>
              )}
              <ol className="timeline">
                {events.data?.pages.flat().map((event) => (
                  <li key={event.id}>
                    <span className="timeline-dot" />
                    <div className="timeline-heading">
                      <strong>{event.event_type}</strong>
                      <span className="mono">#{event.sequence_number}</span>
                    </div>
                    <p className="muted">{date(event.created_at)}</p>
                    <JsonDetails value={event.payload} label="Event payload" />
                  </li>
                ))}
              </ol>
              {events.hasNextPage && (
                <Button
                  variant="outline"
                  disabled={events.isFetchingNextPage}
                  onClick={() => void events.fetchNextPage()}
                >
                  Load more events
                </Button>
              )}
            </Card>
            <Card
              title="Model calls"
              subtitle="Provider, usage, latency, and result evidence."
            >
              <ErrorNotice
                error={calls.error}
                retry={() => void calls.refetch()}
              />
              {calls.isPending && <Loading />}
              {calls.data?.length === 0 && (
                <p className="muted">No model call has been recorded.</p>
              )}
              {calls.data?.map((call) => (
                <div className="model-call" key={call.id}>
                  <div className="actions">
                    <Badge>{call.provider}</Badge>
                    <Badge>{call.status}</Badge>
                  </div>
                  <dl className="definition-list">
                    <div>
                      <dt>Requested model</dt>
                      <dd className="mono">{call.model}</dd>
                    </div>
                    <div>
                      <dt>Actual model</dt>
                      <dd className="mono">
                        {call.actual_model ?? "Not available"}
                      </dd>
                    </div>
                    <div>
                      <dt>Input / output tokens</dt>
                      <dd>
                        {call.input_tokens ?? "—"} / {call.output_tokens ?? "—"}
                      </dd>
                    </div>
                    <div>
                      <dt>Latency</dt>
                      <dd>
                        {call.latency_ms === null
                          ? "Not available"
                          : `${call.latency_ms} ms`}
                      </dd>
                    </div>
                    <div>
                      <dt>Estimated cost</dt>
                      <dd>{cost(call.estimated_cost)}</dd>
                    </div>
                    {call.error_type && (
                      <div>
                        <dt>Error type</dt>
                        <dd>{call.error_type}</dd>
                      </div>
                    )}
                  </dl>
                  <JsonDetails value={call} label="Model-call data" />
                </div>
              ))}
            </Card>
          </div>
          <ToolCallInspector
            org={workspace.id}
            runId={runId}
            active={active(value.status)}
          />
          <Card title="Run record">
            <dl className="definition-list">
              <div>
                <dt>Started</dt>
                <dd>{date(value.started_at)}</dd>
              </div>
              <div>
                <dt>Completed</dt>
                <dd>{date(value.completed_at)}</dd>
              </div>
              <div>
                <dt>Runtime build</dt>
                <dd className="mono">{value.runtime_build_version}</dd>
              </div>
            </dl>
            <JsonDetails value={value} />
          </Card>
        </>
      )}
    </>
  );
}
