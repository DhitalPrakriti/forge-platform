"use client";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, FlaskConical, Play, RotateCcw } from "lucide-react";
import { api } from "@/lib/api/forge";
import { ApiError } from "@/lib/api/client";
import type { RunRequest } from "@/lib/api/types";
import { DEMO_TOOLS } from "@/lib/tool-demo";
import { runSchema } from "@/lib/schemas";
import { rememberRun } from "@/lib/storage";
import { useWorkspace } from "../layout/providers";
import { WorkspaceScreen } from "../workspace/workspace-screen";
import {
  Badge,
  Card,
  ErrorNotice,
  Field,
  Loading,
  PageHeading,
} from "../ui/shared";
import { Button } from "../ui/button";
export function PlaygroundScreen({
  agentId,
  versionId,
}: {
  agentId: string;
  versionId: string;
}) {
  const { workspace } = useWorkspace();
  const router = useRouter();
  const version = useQuery({
    queryKey: [workspace?.id, "version", agentId, versionId],
    queryFn: () => api.version(workspace!.id, agentId, versionId),
    enabled: !!workspace,
  });
  const form = useForm<{ message: string }>({
    resolver: zodResolver(runSchema),
    defaultValues: { message: "" },
  });
  const [attempt, setAttempt] = useState<{
    body: RunRequest;
    key: string;
  } | null>(null);
  const run = useMutation({
    mutationFn: ({ body, key }: { body: RunRequest; key: string }) =>
      api.createRun(workspace!.id, body, key),
    onSuccess: (result) => {
      rememberRun(workspace!.id, result.id);
      router.push(`/runs/${result.id}`);
    },
    onError: (error) => {
      if (
        error instanceof ApiError &&
        error.status >= 400 &&
        error.status < 500
      )
        setAttempt(null);
    },
  });
  if (!workspace) return <WorkspaceScreen />;
  const blocked =
    version.data &&
    !["DRAFT", "STAGING"].includes(version.data.lifecycle_status);
  return (
    <>
      <Link
        href={`/agents/${agentId}/versions/${versionId}`}
        className="back-link"
      >
        <ArrowLeft size={15} />
        Back to version
      </Link>
      <PageHeading
        eyebrow="PLAYGROUND"
        title="Give your agent a test run."
        description="Send one message, then inspect the saved output, events, model calls, and tool calls."
      />
      <ErrorNotice error={version.error} retry={() => void version.refetch()} />
      {version.isPending && <Loading />}
      {version.data && (
        <>
          <div className="metadata-strip">
            <Badge>{version.data.lifecycle_status}</Badge>
            <strong>{version.data.version}</strong>
            <span className="mono">{version.data.primary_model}</span>
          </div>
          <div className="two-column">
            <Card
              title="Test input"
              subtitle="Each submission starts a separate run; this is not a multi-turn conversation."
            >
              <form
                className="form-stack"
                noValidate
                onSubmit={form.handleSubmit(({ message }) => {
                  if (attempt || run.isPending) return;
                  const next = {
                    body: { agent_version_id: versionId, input: { message } },
                    key: crypto.randomUUID(),
                  };
                  setAttempt(next);
                  run.mutate(next);
                })}
              >
                <Field
                  name="message"
                  label="Message"
                  error={form.formState.errors.message?.message}
                >
                  <textarea
                    id="message"
                    rows={9}
                    placeholder="Ask your agent something…"
                    disabled={!!attempt || run.isPending || blocked}
                    {...form.register("message")}
                    aria-invalid={!!form.formState.errors.message}
                  />
                </Field>
                <details className="json-details">
                  <summary>Fake-backend tool examples</summary>
                  <p className="muted">
                    These explicit commands simulate a model request in fake
                    mode. Bind the corresponding tool to this version first; an
                    unbound tool is denied. They do not select or switch the
                    backend provider.
                  </p>
                  <div className="actions">
                    {DEMO_TOOLS.map((demo) => (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        key={demo.name}
                        disabled={!!attempt || run.isPending || blocked}
                        onClick={() =>
                          form.setValue("message", demo.message, {
                            shouldValidate: true,
                          })
                        }
                      >
                        {demo.label}
                      </Button>
                    ))}
                  </div>
                </details>
                <ErrorNotice error={run.error} />
                {blocked && (
                  <p role="alert" className="notice">
                    Only draft and staging versions can be tested.
                  </p>
                )}
                {attempt && run.isError ? (
                  <>
                    <p className="muted">
                      The outcome is uncertain. Retry the exact request with the
                      same key to avoid creating a duplicate run. Keep this page
                      open until it is resolved.
                    </p>
                    <Button type="button" onClick={() => run.mutate(attempt)}>
                      <RotateCcw size={16} />
                      Retry same request
                    </Button>
                  </>
                ) : (
                  <Button
                    type="submit"
                    disabled={run.isPending || run.isSuccess || !!blocked}
                  >
                    <Play size={16} />
                    {run.isPending
                      ? "Running…"
                      : run.isSuccess
                        ? "Opening run…"
                        : "Run agent"}
                  </Button>
                )}
              </form>
            </Card>
            <Card
              title="Execution preview"
              subtitle="What happens when you press Run agent."
            >
              <div className="run-preview">
                <FlaskConical size={30} />
                <h3>One message. A bounded tool loop.</h3>
                <p>
                  The backend chooses the configured fake or Gemini adapter. The
                  result identifies which provider actually ran.
                </p>
              </div>
              <ol className="steps">
                <li>
                  <span>01</span>
                  <div>
                    <strong>Validate and record</strong>
                    <p>Check the version and save a run.</p>
                  </div>
                </li>
                <li>
                  <span>02</span>
                  <div>
                    <strong>Model → Tool Hub → model</strong>
                    <p>
                      Validate permitted tool requests and return their results
                      to the model.
                    </p>
                  </div>
                </li>
                <li>
                  <span>03</span>
                  <div>
                    <strong>Inspect the evidence</strong>
                    <p>Open persisted output, events, and usage.</p>
                  </div>
                </li>
              </ol>
              <p className="inset-note">
                Real provider calls require a key configured on the backend and
                may incur provider charges. Saved budgets are not enforced yet.
              </p>
              {run.isPending && (
                <Loading label="Waiting for the backend. This can take a few minutes…" />
              )}
            </Card>
          </div>
        </>
      )}
    </>
  );
}
