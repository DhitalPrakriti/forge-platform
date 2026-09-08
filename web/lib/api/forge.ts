import { request } from "./client";
import type {
  Agent,
  ModelCall,
  Organization,
  Run,
  RunEvent,
  RunRequest,
  Version,
  VersionInput,
  Tool,
  ToolCall,
  ToolName,
} from "./types";
const json = (body: unknown): RequestInit => ({
  method: "POST",
  body: JSON.stringify(body),
});
const id = encodeURIComponent;
export const api = {
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
