"use client";
import Link from "next/link";
import { DocumentPicker } from "../knowledge/document-picker";
import { ToolCatalog } from "../tools/tool-catalog";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { api } from "@/lib/api/forge";
import type { Version, VersionInput } from "@/lib/api/types";
import { versionSchema, type VersionValues } from "@/lib/schemas";
import { Button } from "../ui/button";
import { Card, ErrorNotice, Field, Loading, JsonDetails } from "../ui/shared";
export function VersionForm({
  org,
  agentId,
  source,
}: {
  org: string;
  agentId: string;
  source?: Version;
}) {
  const router = useRouter();
  const client = useQueryClient();
  const form = useForm<VersionValues>({
    resolver: zodResolver(versionSchema),
    defaultValues: {
      knowledge_document_ids: source?.knowledge_document_ids || [],
      policy_version_ids: source?.policy_version_ids || [],
      tool_version_ids: source?.tool_version_ids || [],
      version: "",
      goal: source?.goal || "",
      instructions: source?.instructions || "",
      primary_model: source?.primary_model || "",
      fallback_models_text: source?.fallback_models.join("\n") || "",
      max_steps: source?.runtime_config.max_steps ?? 12,
      max_runtime_seconds: source?.runtime_config.max_runtime_seconds ?? 180,
      max_cost_per_run_usd:
        source?.budget_config.max_cost_per_run_usd ?? "0.20",
    },
  });
  const create = useMutation({
    mutationFn: (values: VersionValues) => {
      const body: VersionInput = {
        version: values.version,
        goal: values.goal,
        instructions: values.instructions,
        primary_model: values.primary_model,
        runtime_config: {
          max_steps: values.max_steps,
          max_runtime_seconds: values.max_runtime_seconds,
        },
        budget_config: { max_cost_per_run_usd: values.max_cost_per_run_usd },
        runtime_template_revision:
          source?.runtime_template_revision || "standard-agent-v1",
        fallback_models: (values.fallback_models_text || "")
          .split(/[\n,]/)
          .map((v) => v.trim())
          .filter(Boolean),
        knowledge_document_ids: values.knowledge_document_ids || [],
        tool_version_ids: values.tool_version_ids,
        policy_version_ids: values.policy_version_ids,
        evaluation_suite_version_id:
          source?.evaluation_suite_version_id ?? null,
      };
      return api.createVersion(org, agentId, body);
    },
    onSuccess: (version) => {
      void client.invalidateQueries({ queryKey: [org, "versions", agentId] });
      router.push(`/agents/${agentId}/versions/${version.id}`);
    },
  });
  const selectedDocuments =
    useWatch({ control: form.control, name: "knowledge_document_ids" }) || [];
  const enableKnowledge = useMutation({
    mutationFn: () => api.registerTool(org, "search_documents"),
    onSuccess: (tool) => {
      form.setValue(
        "tool_version_ids",
        [...new Set([...form.getValues("tool_version_ids"), tool.id])],
        { shouldDirty: true },
      );
      void client.invalidateQueries({ queryKey: [org, "tools"] });
    },
  });
  const selectedTools =
    useWatch({ control: form.control, name: "tool_version_ids" }) || [];
  const tools = useQuery({
    queryKey: [org, "tools"],
    queryFn: () => api.tools(org),
    refetchOnWindowFocus: "always",
  });
  const policies = useQuery({
    queryKey: [org, "policies"],
    queryFn: () => api.policies(org),
    refetchOnWindowFocus: "always",
  });
  const errors = form.formState.errors;
  return (
    <form
      className="form-stack"
      noValidate
      onSubmit={form.handleSubmit((values) => create.mutate(values))}
    >
      <Card
        title="Behavior"
        subtitle="This configuration becomes immutable when saved."
      >
        <div className="form-stack">
          <Field
            name="version"
            label="Version label"
            error={errors.version?.message}
            hint="A unique label for this agent, such as v1 or support-v2."
          >
            <input
              id="version"
              placeholder="v1"
              {...form.register("version")}
              aria-invalid={!!errors.version}
            />
          </Field>
          <Field name="goal" label="Goal" error={errors.goal?.message}>
            <textarea
              id="goal"
              rows={2}
              placeholder="Help customers understand our product."
              {...form.register("goal")}
              aria-invalid={!!errors.goal}
            />
          </Field>
          <Field
            name="instructions"
            label="Instructions"
            error={errors.instructions?.message}
          >
            <textarea
              id="instructions"
              rows={7}
              placeholder="You are a helpful support assistant. Answer clearly and ask for context when needed."
              {...form.register("instructions")}
              aria-invalid={!!errors.instructions}
            />
          </Field>
        </div>
      </Card>
      <Card
        title="Model & runtime"
        subtitle="A bounded model and tool loop using this exact configuration."
      >
        <div className="form-stack">
          <Field
            name="primary_model"
            label="Model identifier"
            error={errors.primary_model?.message}
            hint="Use a model supported by your backend provider. With the fake backend, this is only a saved label; no provider is called."
          >
            <input
              id="primary_model"
              className="mono"
              placeholder="Enter your provider’s model ID"
              {...form.register("primary_model")}
              aria-invalid={!!errors.primary_model}
            />
          </Field>
          <Field
            name="fallback_models_text"
            label="Fallback models (in order)"
            error={errors.fallback_models_text?.message}
            hint="Optional: one model per line. Queued runs try these after transient failures, before the first successful response. Both providers must be configured on the server."
          >
            <textarea
              id="fallback_models_text"
              rows={3}
              className="mono"
              {...form.register("fallback_models_text")}
            />
          </Field>
          <div className="two-column compact">
            <Field
              name="max_steps"
              label="Maximum steps"
              error={errors.max_steps?.message}
              hint="Maximum model turns. A tool request and final reply need at least two."
            >
              <input
                id="max_steps"
                type="number"
                min={1}
                max={1000}
                {...form.register("max_steps", { valueAsNumber: true })}
              />
            </Field>
            <Field
              name="max_runtime_seconds"
              label="Maximum runtime (seconds)"
              error={errors.max_runtime_seconds?.message}
              hint="The server’s model timeout may impose a lower limit."
            >
              <input
                id="max_runtime_seconds"
                type="number"
                min={1}
                max={86400}
                {...form.register("max_runtime_seconds", {
                  valueAsNumber: true,
                })}
              />
            </Field>
          </div>
          <Field
            name="max_cost_per_run_usd"
            label="Budget per run (USD)"
            error={errors.max_cost_per_run_usd?.message}
            hint="Stops further actions after recorded estimates reach this amount. A call can exceed it; unknown charges are excluded. This is not a billing cap."
          >
            <input
              id="max_cost_per_run_usd"
              inputMode="decimal"
              {...form.register("max_cost_per_run_usd")}
            />
          </Field>
          <div className="inset-note">
            Evaluation suites remain deferred. Existing evaluation bindings are
            preserved when cloning.
          </div>
        </div>
      </Card>
      <Card
        title="Knowledge (optional)"
        subtitle="Choose up to 20 immutable documents this version may search. Leave empty for agents that only use your messages."
      >
        <DocumentPicker
          org={org}
          selected={selectedDocuments}
          onChange={(ids) =>
            form.setValue("knowledge_document_ids", ids, {
              shouldDirty: true,
              shouldValidate: true,
            })
          }
        />
        <div className="actions">
          <Button asChild variant="outline">
            <Link href="/knowledge" target="_blank" rel="noreferrer">
              Upload documents
            </Link>
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={enableKnowledge.isPending}
            onClick={() => enableKnowledge.mutate()}
          >
            Enable Search documents
          </Button>
        </div>
        <ErrorNotice error={enableKnowledge.error} />
        {selectedDocuments.length > 0 &&
          !tools.data?.some(
            (t) =>
              t.name === "search_documents" &&
              selectedTools.includes(t.id) &&
              t.status === "ACTIVE",
          ) && (
            <p role="alert">
              Enable the Search documents tool before saving these document
              bindings. If disabled, re-enable it in Tool Hub.
            </p>
          )}
        <p className="muted">
          Uploads do not change existing versions. Clone a version to change its
          documents. Search returns source passages; it does not create business
          API tools.
        </p>
      </Card>
      <Card
        title="Tool permissions"
        subtitle="Choose the exact registered revisions this new version may request."
      >
        <ErrorNotice error={tools.error} retry={() => void tools.refetch()} />
        {tools.isPending && <Loading />}
        <fieldset className="tool-choices">
          <legend className="sr-only">Allowed tool revisions</legend>
          {tools.data && (
            <ToolCatalog
              tools={tools.data}
              selected={selectedTools}
              onSelect={(ids) =>
                form.setValue("tool_version_ids", ids, {
                  shouldDirty: true,
                  shouldValidate: true,
                })
              }
            />
          )}
          {tools.data &&
            source?.tool_version_ids
              .filter((id) => !tools.data.some((tool) => tool.id === id))
              .map((id) => (
                <label className="tool-choice" key={id}>
                  <input
                    type="checkbox"
                    value={id}
                    {...form.register("tool_version_ids")}
                  />
                  <span className="mono break-word">
                    Unavailable revision: {id}. Remove it before saving.
                  </span>
                </label>
              ))}
        </fieldset>
        {tools.data?.length === 0 && (
          <p className="muted">
            No tools registered yet. You can save a version without tools or
            register demos in Tool Hub.
          </p>
        )}
        {errors.tool_version_ids && (
          <p role="alert" className="field-error">
            Select valid tool revision IDs.
          </p>
        )}
        <div className="actions">
          <Button asChild variant="outline">
            <Link href="/tools" target="_blank" rel="noreferrer">
              Open Tool Hub
            </Link>
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => void tools.refetch()}
          >
            Refresh tools
          </Button>
        </div>
        <p className="inset-note">
          Demo tools use synthetic customers and local data. MCP tools contact
          their configured server and require approval for each call. Selecting
          a tool permits the model to request it; it does not force a call.
        </p>
      </Card>
      {(tools.data?.some(
        (t) => t.name === "issue_refund" && selectedTools.includes(t.id),
      ) ||
        (source?.policy_version_ids.length ?? 0) > 0) && (
        <Card
          title="Refund policy"
          subtitle="Select the immutable policy revision when allowing issue_refund."
        >
          <ErrorNotice
            error={policies.error}
            retry={() => void policies.refetch()}
          />
          {policies.data
            ?.filter((policy) => policy.name === "demo-refund")
            .map((policy) => (
              <label className="tool-choice" key={policy.id}>
                <input
                  type="checkbox"
                  value={policy.id}
                  {...form.register("policy_version_ids")}
                />
                <span>
                  {policy.name} v{policy.version}
                </span>
              </label>
            ))}
          <JsonDetails
            label="Policy technical details"
            value={policies.data?.filter((p) => p.name === "demo-refund") || []}
          />
          {!policies.data?.length && (
            <p>Register the refund policy in Tool Hub, then refresh.</p>
          )}
          <Button
            type="button"
            variant="outline"
            onClick={() => void policies.refetch()}
          >
            Refresh policies
          </Button>
          {errors.policy_version_ids && (
            <p role="alert">Select at most one valid policy revision.</p>
          )}
        </Card>
      )}
      <ErrorNotice error={create.error} />
      <div className="actions">
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? "Saving version…" : "Save immutable version"}
          <ArrowRight size={16} />
        </Button>
        <span className="muted">Saved as DRAFT</span>
      </div>
    </form>
  );
}
