import { type ReactNode, useEffect } from "react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  Boxes,
  BookOpenText,
  Database,
  FlaskConical,
  LayoutDashboard,
  Waypoints,
} from "lucide-react";
import { observedDate } from "@/lib/format";
import { useRuntime } from "@/lib/api";
import { CommandPalette } from "@/components/CommandPalette";
import type { RuntimeInfo } from "@/types";

type NavItem = { to: string; label: string; icon: typeof Boxes; id: string };

const NAV_GROUPS: Array<{ label: string; items: NavItem[] }> = [
  {
    label: "Business",
    items: [
      { to: "/", label: "Command Center", icon: LayoutDashboard, id: "command-center" },
      { to: "/inventory", label: "Inventory", icon: Boxes, id: "inventory" },
    ],
  },
  {
    label: "Intelligence",
    items: [{ to: "/librarian", label: "Librarian", icon: BookOpenText, id: "librarian" }],
  },
  {
    label: "Data",
    items: [
      { to: "/sources", label: "Sources", icon: Database, id: "sources" },
      { to: "/data-health", label: "Data Health", icon: Waypoints, id: "health" },
    ],
  },
  {
    label: "System",
    items: [{ to: "/evaluation", label: "Evaluation", icon: FlaskConical, id: "evaluation" }],
  },
];

/**
 * Persistent orientation: grouped nav + environment + data age, on every page.
 * Page content decides its own header; the shell only frames it.
 */
export function AppShell({ children }: { children: ReactNode }) {
  // One shell-level runtime fetch (60s stale) instead of router state hacks.
  const runtimeQuery = useRuntime();
  const runtime = runtimeQuery.data;
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  // Keep it fresh across route changes; staleTime keeps this cheap.
  useEffect(() => {
    if (runtimeQuery.isStale) void runtimeQuery.refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  return (
    <div className="flex min-h-full">
      <aside
        className="sticky top-0 flex h-screen w-[220px] shrink-0 flex-col border-r py-4"
        style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}
      >
        <div className="flex items-start justify-between gap-1 px-4 pb-4">
          <div>
            <div className="text-[11px] font-medium tracking-wide" style={{ color: "var(--accent-support)" }}>
              Commerce
            </div>
            <div className="text-[14.5px] font-semibold tracking-tight">Data Platform</div>
          </div>
        </div>
        <div className="px-3 pb-4">
          <CommandPalette />
        </div>
        <nav className="flex flex-1 flex-col gap-3 px-2">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="flex flex-col gap-0.5">
              <div className="px-1.5 pb-0.5 text-[11px]" style={{ color: "var(--text-muted)" }}>
                {group.label}
              </div>
              {group.items.map((n) => (
                <RailLink key={n.to} item={n} pathname={pathname} />
              ))}
            </div>
          ))}
        </nav>
        <RuntimeFootnote runtime={runtime} />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <main className="min-w-0 flex-1">{children}</main>
      </div>
      <RuntimeWatchers env={runtime?.environment || "demo"} />
    </div>
  );
}

function RailLink({
  item,
  pathname,
}: {
  item: NavItem;
  pathname: string;
}) {
  const active =
    item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
  const Icon = item.icon;
  return (
    <Link
      key={item.to}
      to={item.to}
      data-testid={`nav-${item.id}`}
      className={
        "flex items-center gap-2.5 rounded px-2.5 py-[7px] text-[13.5px] focus-ring " +
        (active ? "font-medium" : "")
      }
      style={
        active
          ? {
              background: "var(--surface-2)",
              color: "var(--text-primary)",
              boxShadow: "inset 2px 0 0 var(--accent-primary)",
            }
          : { color: "var(--text-muted)" }
      }
    >
      <Icon size={15} strokeWidth={active ? 2 : 1.7} />
      {item.label}
    </Link>
  );
}

/**
 * Runtime/status testids live here so pages don't each fetch /runtime.
 * Hidden from layout; Playwright reads their attributes.
 */
function RuntimeWatchers({ env }: { env: string }) {
  const nav = useNavigate();
  return (
    <>
      <span hidden data-testid="environment" data-env={env} />
      <span hidden data-testid="nav-home-anchor" onClick={() => void nav({ to: "/" })} />
    </>
  );
}

/**
 * Environment + data as-of by default. Model kind is a disclosure, not the
 * default line — demo operators don't need "Fake · test" in the first view.
 */
function RuntimeFootnote({ runtime }: { runtime?: RuntimeInfo }) {
  const env = runtime?.environment || "demo";
  const envLabel =
    env === "private"
      ? "PRIVATE · LOCAL"
      : env === "heldout"
        ? "HELD OUT · EVALUATION"
        : "DEMO · SYNTHETIC";
  const kind = runtime?.model?.kind;
  const kindLabel =
    kind === "fake"
      ? "Fake · test"
      : kind === "local"
        ? `Local · ${runtime?.model?.model || "model"}`
        : kind === "remote"
          ? `Remote · ${runtime?.model?.model || "model"}`
          : null;
  return (
    <div
      className="mx-3 mb-2 mt-auto rounded border px-2.5 py-2"
      data-testid="runtime-footnote"
      style={{ background: "var(--surface-2)", borderColor: "var(--border-subtle)" }}
    >
      <span
        className="text-[11.5px] font-medium tracking-wide"
        style={{
          color:
            env === "private"
              ? "var(--accent-link)"
              : env === "heldout"
                ? "var(--warning)"
                : "var(--text-muted)",
        }}
      >
        {envLabel}
      </span>
      {runtime?.as_of ? (
        <div className="tabular mt-0.5 text-[11.5px]" style={{ color: "var(--text-muted)" }}>
          data as of {observedDate(runtime.as_of) || runtime.as_of}
        </div>
      ) : null}
      {kindLabel ? (
        <details className="mt-0.5" data-testid="model-disclosure">
          <summary
            className="cursor-pointer text-[11.5px]"
            style={{ color: "var(--text-muted)" }}
          >
            Model
          </summary>
          <div className="text-[11.5px]" style={{ color: "var(--text-muted)" }}>
            {kindLabel}
          </div>
        </details>
      ) : null}
    </div>
  );
}
