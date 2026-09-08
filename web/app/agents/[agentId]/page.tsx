import { AgentDetailScreen } from "@/components/agents/agent-screens";
export default async function Page({
  params,
}: {
  params: Promise<{ agentId: string }>;
}) {
  return <AgentDetailScreen {...await params} />;
}
