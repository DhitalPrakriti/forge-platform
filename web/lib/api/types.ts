export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}
export interface Agent {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description: string;
  status: "ACTIVE" | "INACTIVE";
  created_at: string;
  updated_at: string;
}
export interface VersionInput {
  version: string;
  goal: string;
  instructions: string;
  primary_model: string;
  fallback_models: string[];
  runtime_template_revision: string;
  runtime_config: { max_steps: number; max_runtime_seconds: number };
  budget_config: { max_cost_per_run_usd: string };
  tool_version_ids: string[];
  policy_version_ids: string[];
  evaluation_suite_version_id: string | null;
}
export interface Version extends VersionInput {
  id: string;
  agent_id: string;
  created_at: string;
  lifecycle_status:
    | "DRAFT"
    | "STAGING"
    | "EVALUATING"
    | "APPROVED"
    | "PRODUCTION"
    | "DEPRECATED"
    | "ARCHIVED";
}
export interface Run {
  id: string;
  organization_id: string;
  agent_id: string;
  agent_version_id: string;
  status: string;
  state_version: number;
  input: { message: string };
  output: { message?: string } | null;
  error_code: string | null;
  current_step: number;
  model_calls_count: number;
  tool_calls_count: number;
  total_cost: string | null;
  runtime_build_version: string;
  execution_config: {
    provider?: string;
    requested_model?: string;
    budget_enforcement?: string;
    [key: string]: unknown;
  };
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}
export interface RunEvent {
  id: string;
  run_id: string;
  sequence_number: number;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
}
export interface ModelCall {
  id: string;
  run_id: string;
  provider: string;
  model: string;
  actual_model: string | null;
  status: string;
  input_tokens: number | null;
  output_tokens: number | null;
  usage: Record<string, unknown> | null;
  latency_ms: number | null;
  estimated_cost: string | null;
  error_type: string | null;
  created_at: string;
  completed_at: string | null;
}
export interface RunRequest {
  agent_version_id: string;
  input: { message: string };
}

export type ToolName =
  "lookup_customer" | "lookup_transactions" | "create_ticket";
export interface Tool {
  id: string;
  organization_id: string;
  name: ToolName;
  version: string;
  description: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  risk_level: string;
  timeout_seconds: number;
  retry_safe: boolean;
  idempotency_supported: boolean;
  handler_type: string;
  status: "ACTIVE" | "INACTIVE";
  created_at: string;
}
export interface ToolCall {
  id: string;
  run_id: string;
  model_call_id: string;
  call_index: number;
  tool_id: string | null;
  requested_name: string;
  status: string;
  arguments: unknown;
  result: Record<string, unknown> | null;
  error: { code: string } | null;
  decision: string;
  idempotency_key: string;
  request_hash: string;
  latency_ms: number | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}
