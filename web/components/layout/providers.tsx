"use client";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { Organization } from "@/lib/api/types";
import {
  loadWorkspaces,
  saveWorkspaces,
  type WorkspaceState,
} from "@/lib/storage";
interface WorkspaceContext extends WorkspaceState {
  hydrated: boolean;
  storageWarning: boolean;
  select: (id: string | null) => void;
  connect: (org: Organization) => void;
}
const Context = createContext<WorkspaceContext | null>(null);
export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 15_000, retry: false },
          mutations: { retry: false },
        },
      }),
  );
  const [state, setState] = useState<WorkspaceState>({
    workspaces: [],
    selectedId: null,
  });
  const [hydrated, setHydrated] = useState(false);
  const [storageWarning, setStorageWarning] = useState(false);
  useEffect(() => {
    // Browser persistence is read after hydration; server rendering contains no workspace data.
    setState(loadWorkspaces()); // eslint-disable-line react-hooks/set-state-in-effect
    setHydrated(true);
  }, []);
  function update(next: WorkspaceState) {
    setState(next);
    setStorageWarning(!saveWorkspaces(next));
  }
  return (
    <QueryClientProvider client={client}>
      <Context.Provider
        value={{
          ...state,
          hydrated,
          storageWarning,
          select: (selectedId) => update({ ...state, selectedId }),
          connect: (org) =>
            update({
              selectedId: org.id,
              workspaces: [
                org,
                ...state.workspaces.filter((item) => item.id !== org.id),
              ].slice(0, 100),
            }),
        }}
      >
        {children}
      </Context.Provider>
    </QueryClientProvider>
  );
}
export function useWorkspace() {
  const context = useContext(Context);
  if (!context) throw new Error("Workspace provider missing.");
  return {
    ...context,
    workspace: context.workspaces.find((org) => org.id === context.selectedId),
  };
}
