"use client";
import Link from "next/link";
import { History } from "lucide-react";
import { Button } from "../ui/button";
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
      <Button
        variant="ghost"
        size="sm"
        type="button"
        onClick={() => void runs.refetch()}
      >
        Retry latest run link
      </Button>
    );
  const latest = runs.data?.[0];
  if (!latest) return null;
  return (
    <Button asChild variant="outline" size="sm">
      <Link href={`/runs/${latest.id}`}>
        <History size={16} aria-hidden="true" />
        View latest run
      </Link>
    </Button>
  );
}
