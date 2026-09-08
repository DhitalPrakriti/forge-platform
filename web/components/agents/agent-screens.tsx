"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, ArrowRight, Bot, Plus } from "lucide-react";
import { api } from "@/lib/api/forge";
import { agentSchema, type AgentValues } from "@/lib/schemas";
import { date, shortId } from "@/lib/utils";
import { useWorkspace } from "../layout/providers";
import { WorkspaceScreen } from "../workspace/workspace-screen";
import { Button } from "../ui/button";
import {
  Badge,
  Card,
  Empty,
  ErrorNotice,
  Field,
  Loading,
  PageHeading,
  Pagination,
} from "../ui/shared";
export function AgentsScreen() {
  const { workspace } = useWorkspace();
  const [offset, setOffset] = useState(0);
  const agents = useQuery({
    queryKey: [workspace?.id, "agents", offset],
    queryFn: () => api.agents(workspace!.id, offset),
    enabled: !!workspace,
  });
  if (!workspace) return <WorkspaceScreen />;
  return (
    <>
      <PageHeading
        eyebrow="AGENT REGISTRY"
        title="Agents"
        description="Define their purpose. Version their behavior. Inspect every run."
        action={
          <Button asChild>
            <Link href="/agents/new">
              <Plus size={17} />
              Create agent
            </Link>
          </Button>
        }
      />
      <ErrorNotice error={agents.error} retry={() => void agents.refetch()} />
      {agents.isPending && <Loading />}
      {agents.data && (
        <Card
          title="Workspace agents"
          subtitle="Registry records from your selected organization."
        >
          {agents.data.length ? (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Agent</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>
                      <span className="sr-only">Action</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {agents.data.map((agent) => (
                    <tr key={agent.id}>
                      <td>
                        <Link
                          href={`/agents/${agent.id}`}
                          className="agent-cell"
                        >
                          <span className="resource-icon">
                            <Bot size={20} />
                          </span>
                          <span>
                            <strong>{agent.name}</strong>
                            <span className="muted line-clamp-2">
                              {agent.description || agent.slug}
                            </span>
                          </span>
                        </Link>
                      </td>
                      <td>
                        <Badge>{agent.status}</Badge>
                      </td>
                      <td className="muted">{date(agent.created_at)}</td>
                      <td>
                        <Link
                          href={`/agents/${agent.id}`}
                          aria-label={`Open ${agent.name}`}
                        >
                          <ArrowRight size={18} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty title="Your next agent starts here.">
              <p>Create an agent, then add its first version.</p>
              <Button asChild>
                <Link href="/agents/new">
                  <Plus size={16} />
                  Create agent
                </Link>
              </Button>
            </Empty>
          )}
          <Pagination
            offset={offset}
            count={agents.data.length}
            onChange={setOffset}
          />
        </Card>
      )}
    </>
  );
}
export function CreateAgentScreen() {
  const { workspace } = useWorkspace();
  const router = useRouter();
  const client = useQueryClient();
  const form = useForm<AgentValues>({
    resolver: zodResolver(agentSchema),
    defaultValues: { name: "", slug: "", description: "" },
  });
  const create = useMutation({
    mutationFn: (values: AgentValues) => api.createAgent(workspace!.id, values),
    onSuccess: (agent) => {
      void client.invalidateQueries({ queryKey: [workspace!.id, "agents"] });
      router.push(`/agents/${agent.id}/versions/new`);
    },
  });
  if (!workspace) return <WorkspaceScreen />;
  return (
    <>
      <Link href="/agents" className="back-link">
        <ArrowLeft size={15} />
        Agent registry
      </Link>
      <PageHeading
        eyebrow="STEP 1 / IDENTITY"
        title="Create an agent"
        description="Start with its identity. You’ll define instructions and a model in the next step."
      />
      <div className="form-layout">
        <Card title="Agent identity">
          <form
            className="form-stack"
            noValidate
            onSubmit={form.handleSubmit((values) => create.mutate(values))}
          >
            <Field
              name="agent-name"
              label="Agent name"
              error={form.formState.errors.name?.message}
            >
              <input
                id="agent-name"
                placeholder="Support assistant"
                {...form.register("name")}
                aria-invalid={!!form.formState.errors.name}
              />
            </Field>
            <Field
              name="agent-slug"
              label="Agent slug"
              error={form.formState.errors.slug?.message}
              hint="Unique in this workspace. It cannot be changed later."
            >
              <input
                id="agent-slug"
                placeholder="support-assistant"
                {...form.register("slug")}
                aria-invalid={!!form.formState.errors.slug}
              />
            </Field>
            <Field
              name="agent-description"
              label="Description (optional)"
              error={form.formState.errors.description?.message}
            >
              <textarea
                id="agent-description"
                rows={4}
                placeholder="What will this agent help with?"
                {...form.register("description")}
              />
            </Field>
            <ErrorNotice error={create.error} />
            <div className="actions">
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "Creating…" : "Create agent & add version"}
                <ArrowRight size={16} />
              </Button>
              <Button asChild variant="ghost">
                <Link href="/agents">Cancel</Link>
              </Button>
            </div>
          </form>
        </Card>
        <div className="aside-note">
          <Bot size={24} />
          <h2>Identity stays. Versions evolve.</h2>
          <p>
            An agent is the stable registry entry. Its versions contain the
            goal, instructions, model, and runtime configuration.
          </p>
          <p>
            This step creates the agent immediately. You can come back and
            finish its first version at any time.
          </p>
        </div>
      </div>
    </>
  );
}
export function AgentDetailScreen({ agentId }: { agentId: string }) {
  const { workspace } = useWorkspace();
  const [offset, setOffset] = useState(0);
  const agent = useQuery({
    queryKey: [workspace?.id, "agent", agentId],
    queryFn: () => api.agent(workspace!.id, agentId),
    enabled: !!workspace,
  });
  const versions = useQuery({
    queryKey: [workspace?.id, "versions", agentId, offset],
    queryFn: () => api.versions(workspace!.id, agentId, offset),
    enabled: !!workspace && !!agent.data,
  });
  if (!workspace) return <WorkspaceScreen />;
  return (
    <>
      <Link href="/agents" className="back-link">
        <ArrowLeft size={15} />
        Agent registry
      </Link>
      <ErrorNotice error={agent.error} retry={() => void agent.refetch()} />
      {agent.isPending && <Loading />}
      {agent.data && (
        <>
          <PageHeading
            eyebrow="AGENT"
            title={agent.data.name}
            description={
              agent.data.description ||
              "Add a version to define how this agent behaves."
            }
            action={
              <Button asChild>
                <Link href={`/agents/${agentId}/versions/new`}>
                  <Plus size={16} />
                  Create version
                </Link>
              </Button>
            }
          />
          <div className="metadata-strip">
            <Badge>{agent.data.status}</Badge>
            <span className="mono">{agent.data.slug}</span>
            <span className="muted">
              ID{" "}
              <span className="mono" title={agentId}>
                {shortId(agentId)}
              </span>
            </span>
            <span className="muted">Created {date(agent.data.created_at)}</span>
          </div>
          <Card
            title="Immutable versions"
            subtitle="Each version is a saved configuration. Create a new version to change behavior."
          >
            <ErrorNotice
              error={versions.error}
              retry={() => void versions.refetch()}
            />
            {versions.isPending && <Loading />}
            {versions.data && (
              <>
                {versions.data.length ? (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Version</th>
                          <th>Lifecycle</th>
                          <th>Model</th>
                          <th>Created</th>
                        </tr>
                      </thead>
                      <tbody>
                        {versions.data.map((version) => (
                          <tr key={version.id}>
                            <td>
                              <Link
                                className="text-link"
                                href={`/agents/${agentId}/versions/${version.id}`}
                              >
                                {version.version}
                                <ArrowRight size={14} />
                              </Link>
                            </td>
                            <td>
                              <Badge>{version.lifecycle_status}</Badge>
                            </td>
                            <td className="mono">{version.primary_model}</td>
                            <td className="muted">
                              {date(version.created_at)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <Empty title="No versions yet">
                    <p>Give your agent its goal, instructions, and model.</p>
                    <Button asChild>
                      <Link href={`/agents/${agentId}/versions/new`}>
                        Create first version
                        <ArrowRight size={16} />
                      </Link>
                    </Button>
                  </Empty>
                )}
                <Pagination
                  offset={offset}
                  count={versions.data.length}
                  onChange={setOffset}
                />
              </>
            )}
          </Card>
        </>
      )}
    </>
  );
}
