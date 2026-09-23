import { request } from "./client";
import type {
  KnowledgeDocument,
  KnowledgeResult,
  Agent,
  Policy,
  Approval,
  ModelCall,
  ModelHealth,
  Organization,
  Run,
  RunEvent,
  RunRequest,
  Version,
  VersionInput,
  Tool,
  ToolCall,
  ToolName,
  MCPDiscoveredTool,
} from "./types";
const json = (body: unknown): RequestInit => ({
  method: "POST",
  body: JSON.stringify(body),
});
const id = encodeURIComponent;
export const api = {
  versionRuns: (org: string, versionId: string, offset = 0, limit = 20) =>
    request<Run[]>(
      `/agent-versions/${id(versionId)}/runs?limit=${limit}&offset=${offset}`,
      org,
    ),
  documents: (org: string, offset = 0) =>
    request<KnowledgeDocument[]>(
      `/knowledge/documents?limit=100&offset=${offset}`,
      org,
    ),
  uploadDocument: (
    org: string,
    body: { title: string; filename: string; content_base64: string },
  ) => request<KnowledgeDocument>("/knowledge/documents", org, json(body)),
  searchDocuments: (org: string, document_ids: string[], query: string) =>
    request<KnowledgeResult>(
      "/knowledge/search",
      org,
      json({ document_ids, query }),
    ),

  modelHealth: (org: string) => request<ModelHealth[]>("/models/health", org),
  mcpServers: (org: string) => request<{ name: string }[]>("/mcp/servers", org),
  discoverMcp: (org: string, server: string) =>
    request<MCPDiscoveredTool[]>(`/mcp/servers/${id(server)}/tools`, org),
  registerMcp: (org: string, server: string, tool: MCPDiscoveredTool) =>
    request<Tool>(
      "/mcp/tools",
      org,
      json({
        server,
        remote_name: tool.tool.name,
        fingerprint: tool.fingerprint,
      }),
    ),
  cancelRun: (org: string, runId: string) =>
    request<Run>(`/runs/${id(runId)}/cancel`, org, { method: "POST" }),
  retryRun: (org: string, runId: string, key: string) =>
    request<Run>(`/runs/${id(runId)}/retry`, org, {
      method: "POST",
      headers: { "Idempotency-Key": key },
    }),
  policies: (org: string) => request<Policy[]>("/policies?limit=100", org),
  registerPolicy: (org: string) =>
    request<Policy>("/policies", org, { method: "POST" }),
  approvals: (org: string, runId: string) =>
    request<Approval[]>(`/approvals?run_id=${id(runId)}&limit=100`, org),
  decideApproval: (
    org: string,
    approvalId: string,
    verdict: "approve" | "deny",
    reason: string,
    token: string,
  ) =>
    request<Approval>(`/approvals/${id(approvalId)}/${verdict}`, org, {
      ...json({ reason }),
      headers: { Authorization: `Bearer ${token}` },
    }),
  resumeRun: (org: string, runId: string, token: string) =>
    request<Run>(`/runs/${id(runId)}/resume`, org, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }),
  tools: (org: string) => request<Tool[]>("/tools?limit=100", org),
  registerTool: (org: string, name: ToolName) =>
    request<Tool>("/tools", org, json({ name, version: "1.0.0" })),
  patchTool: (org: string, toolId: string, status: Tool["status"]) =>
    request<Tool>(`/tools/${id(toolId)}`, org, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  toolCalls: (org: string, runId: string) =>
    request<ToolCall[]>(`/runs/${id(runId)}/tool-calls?limit=100`, org),
  health: () => request<{ status: string }>("/health/ready"),
  createOrganization: (body: { name: string; slug: string }) =>
    request<Organization>("/organizations", undefined, json(body)),
  organization: (org: string) =>
    request<Organization>("/organizations/current", org),
  agents: (org: string, offset = 0) =>
    request<Agent[]>(`/agents?limit=20&offset=${offset}`, org),
  agent: (org: string, agentId: string) =>
    request<Agent>(`/agents/${id(agentId)}`, org),
  createAgent: (
    org: string,
    body: { name: string; slug: string; description: string },
  ) => request<Agent>("/agents", org, json(body)),
  versions: (org: string, agentId: string, offset = 0) =>
    request<Version[]>(
      `/agents/${id(agentId)}/versions?limit=20&offset=${offset}`,
      org,
    ),
  version: (org: string, agentId: string, versionId: string) =>
    request<Version>(`/agents/${id(agentId)}/versions/${id(versionId)}`, org),
  createVersion: (org: string, agentId: string, body: VersionInput) =>
    request<Version>(`/agents/${id(agentId)}/versions`, org, json(body)),
  archive: (org: string, versionId: string) =>
    request<Version>(`/agent-versions/${id(versionId)}/archive`, org, {
      method: "POST",
    }),
  createRun: (org: string, body: RunRequest, key: string) =>
    request<Run>("/runs", org, {
      ...json(body),
      headers: { "Idempotency-Key": key },
    }),
  run: (org: string, runId: string) => request<Run>(`/runs/${id(runId)}`, org),
  events: (org: string, runId: string, after = -1) =>
    request<RunEvent[]>(
      `/runs/${id(runId)}/events?limit=100&after=${after}`,
      org,
    ),
  modelCalls: (org: string, runId: string) =>
    request<ModelCall[]>(`/runs/${id(runId)}/model-calls`, org),
};
