import { CreateVersionScreen } from "@/components/agents/version-screens";
export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ agentId: string }>;
  searchParams: Promise<{ from?: string }>;
}) {
  const { agentId } = await params;
  const { from } = await searchParams;
  return <CreateVersionScreen agentId={agentId} sourceId={from} />;
}
