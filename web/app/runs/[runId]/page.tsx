import { RunDetailScreen } from "@/components/runs/run-detail-screen";
export default async function Page({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  return <RunDetailScreen {...await params} />;
}
