"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/forge";

export function LatestRunLink({
  org,
  versionId,
}: {
  org: string;
  versionId: string;
}) {
  const runs = useQuery({
    queryKey: [org, "latest-version-run", versionId],
    queryFn: () => api.versionRuns(org, versionId, 0, 1),
    refetchOnMount: "always",
  });
  if (runs.isError)
    return (
      <button type="button" onClick={() => void runs.refetch()}>
        Retry latest run link
      </button>
    );
  const latest = runs.data?.[0];
  if (!latest) return null;
  return <Link href={`/runs/${latest.id}`}>View latest run →</Link>;
}
