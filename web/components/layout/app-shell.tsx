"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  Bot,
  Boxes,
  ChevronsUpDown,
  LayoutDashboard,
  Play,
  Settings2,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import type { ReactNode } from "react";
import { api } from "@/lib/api/forge";
import { useWorkspace } from "./providers";
import { Badge, Loading } from "../ui/shared";
const navigation = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/runs", label: "Runs", icon: Play },
  { href: "/tools", label: "Tools", icon: Wrench },
  { href: "/workspace", label: "Workspace", icon: Settings2 },
];
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { workspace, workspaces, select, hydrated, storageWarning } =
    useWorkspace();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 15_000,
  });
  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <aside className="sidebar">
        <Link href="/" className="brand" aria-label="FORGE home">
          <span className="brand-symbol">
            <Boxes size={23} />
          </span>
          FORGE<span className="brand-dot">®</span>
        </Link>
        <div className="sidebar-caption">BUILD & OPERATE</div>
        <nav aria-label="Main navigation">
          {navigation.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={`nav-link ${(href === "/" ? pathname === href : pathname.startsWith(href)) ? "active" : ""}`}
              aria-current={
                (href === "/" ? pathname === href : pathname.startsWith(href))
                  ? "page"
                  : undefined
              }
            >
              <Icon size={18} />
              {label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-future">
          <ShieldCheck size={19} />
          <strong>From draft to production</strong>
          <p>
            Refund approvals are available in each run. Evaluations and
            deployments arrive later.
          </p>
          <span className="tiny-label">ON THE ROADMAP</span>
        </div>
        <div className="sidebar-bottom">
          <span className="status-dot" />
          Local development<span className="mono">v0.1</span>
        </div>
      </aside>
      <div className="main-column">
        <div className="topbar">
          <div className="workspace-select">
            <label htmlFor="workspace-select">
              <Boxes size={17} />
              <span className="sr-only">Active workspace</span>
            </label>
            <select
              id="workspace-select"
              value={workspace?.id || ""}
              onChange={(event) => {
                select(event.target.value || null);
                router.push("/");
              }}
            >
              <option value="">Choose a workspace</option>
              {workspaces.map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name}
                </option>
              ))}
            </select>
            <ChevronsUpDown size={13} />
          </div>
          <div className="topbar-right">
            <span className={`health ${health.isError ? "health-error" : ""}`}>
              <Activity size={15} />
              {health.isPending
                ? "Checking API"
                : health.isError
                  ? "API unavailable"
                  : "API ready"}
            </span>
            <Badge>LOCAL</Badge>
            <a
              href="http://127.0.0.1:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="docs-link"
            >
              API docs
              <ArrowUpRight size={14} />
            </a>
          </div>
        </div>
        <main id="main" className="main-content">
          {storageWarning && (
            <p role="status" className="notice">
              Browser storage is unavailable. Workspace selection lasts only for
              this visit.
            </p>
          )}
          {hydrated ? (
            <div key={workspace?.id || "no-workspace"}>{children}</div>
          ) : (
            <Loading label="Preparing your workspace…" />
          )}
        </main>
        <footer className="footer">
          <span>FORGE / Agent operations</span>
          <span>Local console · Phase 5 backend</span>
        </footer>
      </div>
    </div>
  );
}
