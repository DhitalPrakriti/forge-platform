"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/forge";
import { date, shortId } from "@/lib/utils";
import { Badge, Card, ErrorNotice, Loading } from "../ui/shared";
import { Button } from "../ui/button";

export function VersionRuns({
  org,
  versionId,
}: {
  org: string;
  versionId: string;
}) {
  const [offset, setOffset] = useState(0);
  const runs = useQuery({
    queryKey: [org, "version-runs", versionId, offset],
    queryFn: () => api.versionRuns(org, versionId, offset),
    refetchOnMount: "always",
  });
  return (
    <Card
      title="Runs for this version"
      subtitle="Saved execution history from the backend. Open a run to see its input, output, model calls, and tool activity."
    >
      <ErrorNotice error={runs.error} retry={() => void runs.refetch()} />
      {runs.isPending && <Loading />}
      {runs.data?.length === 0 && (
        <p>No runs on this page. Use Test version to start a run.</p>
      )}
      <div className="form-stack">
        {runs.data?.map((run) => (
          <div key={run.id}>
            <Link href={`/runs/${run.id}`} className="back-link">
              Open run {shortId(run.id)} →
            </Link>
            <div className="metadata-strip">
              <Badge>{run.status}</Badge>
              <span>{date(run.created_at)}</span>
            </div>
            <p className="break-word">
              {run.input.message.slice(0, 180)}
              {run.input.message.length > 180 ? "…" : ""}
            </p>
          </div>
        ))}
      </div>
      <div className="actions">
        <Button
          variant="outline"
          disabled={offset === 0}
          onClick={() => setOffset(offset - 20)}
        >
          Newer runs
        </Button>
        <Button
          variant="outline"
          disabled={runs.data?.length !== 20}
          onClick={() => setOffset(offset + 20)}
        >
          Older runs
        </Button>
        <Button variant="ghost" onClick={() => void runs.refetch()}>
          Refresh runs
        </Button>
      </div>
    </Card>
  );
}
