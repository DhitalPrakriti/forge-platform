import { VersionDetailScreen } from "@/components/agents/version-screens";
export default async function Page({
  params,
}: {
  params: Promise<{ agentId: string; versionId: string }>;
}) {
  return <VersionDetailScreen {...await params} />;
}
