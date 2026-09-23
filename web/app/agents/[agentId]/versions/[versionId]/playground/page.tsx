import { PlaygroundScreen } from "@/components/runs/playground-screen";
export default async function Page({
  params,
}: {
  params: Promise<{ agentId: string; versionId: string }>;
}) {
  return <PlaygroundScreen {...await params} />;
}
