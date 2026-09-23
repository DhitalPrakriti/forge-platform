"use client";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueries } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight } from "lucide-react";
import { api } from "@/lib/api/forge";
import { organizationIdSchema } from "@/lib/schemas";
import { loadRunIds } from "@/lib/storage";
import { cost, date, shortId } from "@/lib/utils";
import { useWorkspace } from "../layout/providers";
import { WorkspaceScreen } from "../workspace/workspace-screen";
import {
  Badge,
  Card,
  Empty,
  ErrorNotice,
  Field,
  Loading,
  PageHeading,
} from "../ui/shared";
import { Button } from "../ui/button";
export function RunsScreen() {
  const { workspace } = useWorkspace();
  const router = useRouter();
  const [ids] = useState(() => (workspace ? loadRunIds(workspace.id) : []));
  const records = useQueries({
    queries: ids.map((runId) => ({
      queryKey: [workspace?.id, "run", runId],
      queryFn: () => api.run(workspace!.id, runId),
      enabled: !!workspace,
    })),
  });
  const form = useForm<{ id: string }>({
    resolver: zodResolver(organizationIdSchema),
    defaultValues: { id: "" },
  });
  if (!workspace) return <WorkspaceScreen />;
  return (
    <>
      <PageHeading
        eyebrow="EXECUTION HISTORY"
        title="Runs"
        description="Inspect what your agents did, using records saved by the backend."
      />
      <Card
        title="Open a run"
        subtitle="Paste a run ID returned by the API or shared from this console."
      >
        <form
          noValidate
          className="inline-form"
          onSubmit={form.handleSubmit(({ id }) => router.push(`/runs/${id}`))}
        >
          <Field
            name="run-id"
            label="Run ID"
            error={
              form.formState.errors.id ? "Enter a valid run UUID." : undefined
            }
          >
            <input
              id="run-id"
              className="mono"
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              {...form.register("id")}
            />
          </Field>
          <Button type="submit">
            Open run
            <ArrowRight size={16} />
          </Button>
        </form>
      </Card>
      <Card
        title="Runs opened in this browser"
        subtitle="Up to 50 recent IDs for this workspace. This is not a complete organization-wide history."
      >
        {!ids.length ? (
          <Empty title="No runs opened yet">
            <p>Choose an agent version and send a test message.</p>
            <Button asChild>
              <Link href="/agents">
                Choose an agent
                <ArrowRight size={16} />
              </Link>
            </Button>
          </Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Status</th>
                  <th>Provider</th>
                  <th>Cost</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {records.map((record, index) => (
                  <tr key={ids[index]}>
                    <td>
                      <Link
                        className="text-link mono"
                        href={`/runs/${ids[index]}`}
                      >
                        {shortId(ids[index])}
                        <ArrowRight size={13} />
                      </Link>
                    </td>
                    {record.isPending ? (
                      <td colSpan={4}>
                        <Loading />
                      </td>
                    ) : record.isError ? (
                      <td colSpan={4}>
                        <ErrorNotice
                          error={record.error}
                          retry={() => void record.refetch()}
                        />
                      </td>
                    ) : (
                      <>
                        <td>
                          <Badge>{record.data!.status}</Badge>
                        </td>
                        <td>
                          <Badge>
                            {record.data!.execution_config.provider ||
                              "UNKNOWN"}
                          </Badge>
                        </td>
                        <td>{cost(record.data!.total_cost)}</td>
                        <td className="muted">
                          {date(record.data!.created_at)}
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
