import { z } from "zod";
const workspaceSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  slug: z.string(),
  created_at: z.string(),
});
const savedSchema = z.object({
  workspaces: z.array(workspaceSchema).max(100),
  selectedId: z.string().uuid().nullable(),
});
export type WorkspaceState = z.infer<typeof savedSchema>;
export function loadWorkspaces(): WorkspaceState {
  try {
    return savedSchema.parse(
      JSON.parse(localStorage.getItem("forge.workspaces.v1") || ""),
    );
  } catch {
    return { workspaces: [], selectedId: null };
  }
}
export function saveWorkspaces(value: WorkspaceState): boolean {
  try {
    localStorage.setItem("forge.workspaces.v1", JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}
export function loadRunIds(org: string): string[] {
  try {
    return z
      .array(z.string().uuid())
      .max(50)
      .parse(JSON.parse(localStorage.getItem(`forge.runs.v1.${org}`) || "[]"));
  } catch {
    return [];
  }
}
export function rememberRun(org: string, runId: string): boolean {
  try {
    localStorage.setItem(
      `forge.runs.v1.${org}`,
      JSON.stringify(
        [runId, ...loadRunIds(org).filter((id) => id !== runId)].slice(0, 50),
      ),
    );
    return true;
  } catch {
    return false;
  }
}
