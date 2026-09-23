"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/forge";
import { Badge, Card, ErrorNotice, Loading } from "../ui/shared";
import { Button } from "../ui/button";
export function ModelHealthPanel({ org }: { org: string }) {
  const health = useQuery({
    queryKey: [org, "model-health"],
    queryFn: () => api.modelHealth(org),
  });
  return (
    <Card
      title="Model availability"
      subtitle="Observed calls in this workspace. No paid monitoring requests."
    >
      <ErrorNotice error={health.error} retry={() => void health.refetch()} />
      {health.isPending && <Loading />}
      {health.data?.length === 0 && (
        <p className="muted">
          No provider calls observed yet. Availability is unknown.
        </p>
      )}
      {health.data?.map((item) => (
        <div className="model-call" key={`${item.provider}:${item.model}`}>
          <div className="actions">
            <strong className="mono">{item.model}</strong>
            <Badge>{item.state}</Badge>
          </div>
          <p className="muted">
            {item.provider} · {item.failures} consecutive transient failures
          </p>
          <p>
            {item.state === "CLOSED"
              ? "Calls permitted; this is not a guarantee of availability."
              : item.state === "OPEN"
                ? "Temporarily skipped. A new call may probe after the cooldown."
                : "One recovery probe permitted at a time."}
          </p>
          {item.open_until && (
            <p className="muted">
              Cooldown until {new Date(item.open_until).toLocaleString()}
            </p>
          )}
          {item.last_error && (
            <p className="mono">Last error: {item.last_error}</p>
          )}
          <p className="muted">
            Last observation:{" "}
            {item.last_observed_at
              ? new Date(item.last_observed_at).toLocaleString()
              : "None"}
          </p>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        onClick={() => void health.refetch()}
      >
        Refresh model availability
      </Button>
    </Card>
  );
}
