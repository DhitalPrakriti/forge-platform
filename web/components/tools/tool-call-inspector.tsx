"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/forge";
import { date } from "@/lib/utils";
import { Badge, Card, ErrorNotice, JsonDetails, Loading } from "../ui/shared";
export function ToolCallInspector({
  org,
  runId,
  active,
}: {
  org: string;
  runId: string;
  active: boolean;
}) {
  const calls = useQuery({
    queryKey: [org, "tool-calls", runId],
    queryFn: () => api.toolCalls(org, runId),
    refetchInterval: active ? 2000 : false,
  });
  return (
    <Card
      title="Tool calls"
      subtitle="Validated function requests, exact tool IDs, decisions, and saved results."
    >
      <ErrorNotice error={calls.error} retry={() => void calls.refetch()} />
      {calls.isPending && <Loading />}
      {calls.data?.length === 0 && (
        <p className="muted">No tool requests were recorded for this run.</p>
      )}
      {calls.data?.map((call) => (
        <article className="model-call tool-call" key={call.id}>
          <div className="actions">
            <strong className="mono">{call.requested_name}</strong>
            <Badge>{call.status}</Badge>
            <Badge>{call.decision}</Badge>
          </div>
          <dl className="definition-list">
            <div>
              <dt>Tool revision ID</dt>
              <dd className="mono">
                {call.tool_id || "No permitted revision"}
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
              <dt>Completed</dt>
              <dd>{date(call.completed_at)}</dd>
            </div>
          </dl>
          {call.error && (
            <p role="alert" className="error-notice">
              {call.error.code}
            </p>
          )}
          <div className="two-column compact">
            <div>
              <h3>Arguments</h3>
              <pre>{JSON.stringify(call.arguments, null, 2)}</pre>
            </div>
            <div>
              <h3>Result</h3>
              <pre>
                {call.result
                  ? JSON.stringify(call.result, null, 2)
                  : "No result recorded."}
              </pre>
            </div>
          </div>
          <JsonDetails value={call} label="Tool-call record" />
        </article>
      ))}
    </Card>
  );
}
