"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Bot,
  FileCode2,
  Play,
  Radio,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import { api } from "@/lib/api/forge";
import { useWorkspace } from "../layout/providers";
import { WorkspaceScreen } from "../workspace/workspace-screen";
import { Badge, Card, ErrorNotice, Loading, PageHeading } from "../ui/shared";
import { Button } from "../ui/button";
export function OverviewScreen() {
  const { workspace } = useWorkspace();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const agents = useQuery({
    queryKey: [workspace?.id, "agents", 0],
    queryFn: () => api.agents(workspace!.id),
    enabled: !!workspace,
  });
  if (!workspace) return <WorkspaceScreen />;
  return (
    <>
      <PageHeading
        eyebrow="WORKSPACE OVERVIEW"
        title="Agent operations"
        description={`Your command center for building, testing, and inspecting agents in ${workspace.name}.`}
        action={
          <Button asChild>
            <Link href="/agents/new">
              <Bot size={16} />
              Create agent
            </Link>
          </Button>
        }
      />
      <section className="overview-banner">
        <div>
          <span className="tiny-label">BUILD → VERSION → RUN → INSPECT</span>
          <h2>Build with purpose. Run with confidence.</h2>
          <p>
            Turn instructions into immutable versions. Test their behavior,
            review tool decisions, and follow every run from input to outcome.
          </p>
          <Button asChild variant="outline">
            <Link href="/agents">
              Open agent registry
              <ArrowRight size={16} />
            </Link>
          </Button>
        </div>
        <div className="pipeline-visual" aria-label="Agent execution workflow">
          <span>
            <Bot size={25} />
            <small>DEFINE</small>
          </span>
          <i />
          <span>
            <FileCode2 size={25} />
            <small>VERSION</small>
          </span>
          <i />
          <span>
            <Play size={25} />
            <small>EXECUTE</small>
          </span>
        </div>
      </section>
      <div className="summary-grid">
        <Card>
          <div className="metric-label">
            <Radio size={17} />
            Backend readiness
          </div>
          <div className="metric-value">
            {health.isPending
              ? "Checking"
              : health.isError
                ? "Unavailable"
                : "Ready"}
          </div>
          <p className="muted">API and database connection</p>
        </Card>
        <Card>
          <div className="metric-label">
            <Bot size={17} />
            Agent registry
          </div>
          <div className="metric-value">
            {agents.data
              ? `${agents.data.length}${agents.data.length === 20 ? "+" : ""}`
              : "—"}
          </div>
          <p className="muted">Agents on the first page</p>
        </Card>
        <Card>
          <div className="metric-label">
            <FileCode2 size={17} />
            Current runtime
          </div>
          <div className="metric-value">Model + tools</div>
          <p className="muted">Provider configured on the backend</p>
        </Card>
      </div>
      <div className="operation-links">
        <Link href="/agents" className="operation-link">
          <Bot size={20} />
          <div>
            <strong>Agent registry</strong>
            <span>Manage identities and versions</span>
          </div>
          <ArrowRight size={16} />
        </Link>
        <Link href="/runs" className="operation-link">
          <ShieldCheck size={20} />
          <div>
            <strong>Execution & approvals</strong>
            <span>Inspect runs and review actions</span>
          </div>
          <ArrowRight size={16} />
        </Link>
        <Link href="/tools" className="operation-link">
          <Wrench size={20} />
          <div>
            <strong>Tool registry</strong>
            <span>Inspect capabilities and risk</span>
          </div>
          <ArrowRight size={16} />
        </Link>
      </div>
      <div className="two-column">
        <Card
          title="Continue building"
          subtitle="The first agents in your registry."
        >
          <ErrorNotice
            error={agents.error}
            retry={() => void agents.refetch()}
          />
          {agents.isPending && <Loading />}
          {agents.data?.length === 0 && (
            <p className="muted">
              Your registry is empty. Create your first agent to begin.
            </p>
          )}
          {agents.data?.slice(0, 4).map((agent) => (
            <Link
              className="resource-row"
              href={`/agents/${agent.id}`}
              key={agent.id}
            >
              <span className="resource-icon">
                <Bot size={19} />
              </span>
              <span className="resource-label">
                <strong>{agent.name}</strong>
                <span className="muted">{agent.slug}</span>
              </span>
              <Badge>{agent.status}</Badge>
              <ArrowRight size={16} />
            </Link>
          ))}
        </Card>
        <Card
          title="What you can test today"
          subtitle="A small, complete development loop."
        >
          <ol className="steps">
            <li>
              <span>01</span>
              <div>
                <strong>Define an agent</strong>
                <p>Give it a name and a purpose.</p>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                <strong>Save an immutable version</strong>
                <p>Set its goal, instructions, and model.</p>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                <strong>Run and inspect</strong>
                <p>See output, events, and model and tool evidence.</p>
              </div>
            </li>
          </ol>
          <p className="subtle-note">
            Demo tool calling is available. Evaluations and deployment are not
            implemented yet. Fake runs are clearly marked in their results.
          </p>
        </Card>
      </div>
    </>
  );
}
