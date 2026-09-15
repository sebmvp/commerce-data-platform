import { type ReactNode } from "react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  BookOpenText,
  Boxes,
  FlaskConical,
  HeartPulse,
  LayoutDashboard,
} from "lucide-react";
import { observedDate } from "@/lib/format";
import type { RuntimeInfo } from "@/types";

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard, id: "overview" },
  { to: "/inventory", label: "Inventory", icon: Boxes, id: "inventory" },
  { to: "/librarian", label: "Librarian", icon: BookOpenText, id: "librarian" },
  { to: "/evaluation", label: "Evaluation", icon: FlaskConical, id: "evaluation" },
  { to: "/data-health", label: "Data Health", icon: HeartPulse, id: "health" },
] as const;

/**
 * Persistent orientation: nav + environment + model + data age, on every page.
 * Page content decides its own header; the shell only frames it.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const runtime = useRouterState({
    select: (s) => (s.location.state ?? {}) as Partial<RuntimeInfo>,
  });
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const env = runtime?.environment || "demo";
  return (
    <div className="flex min-h-full">
      <aside
        className="sticky top-0 flex h-screen w-[200px] shrink-0 flex-col border-r py-4"
        style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}
      >
        <div className="px-4 pb-3">
          <div className="text-[11px] font-medium tracking-wide" style={{ color: "var(--accent-support)" }}>
            Commerce
          </div>
          <div className="text-[14.5px] font-semibold tracking-tight">Data Platform</div>
        </div>
        <nav className="flex flex-1 flex-col gap-0.5 px-2">
          {NAV.map((n) => {
            const Icon = n.icon;
            const active =
              n.to === "/" ? pathname === "/" : pathname.startsWith(n.to);
            return (
              <Link
                key={n.to}
                to={n.to}
                data-testid={`nav-${n.id}`}
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
                {n.label}
              </Link>
            );
          })}
        </nav>
        <RuntimeFootnote runtime={runtime as RuntimeInfo | undefined} />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <main className="min-w-0 flex-1">{children}</main>
      </div>
      <RuntimeWatchers env={env} />
    </div>
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

type FootnoteProps = { runtime?: RuntimeInfo };

function RuntimeFootnote({ runtime }: FootnoteProps) {
  const env = runtime?.environment || "demo";
  const kind = runtime?.model?.kind || "fake";
  const envLabel =
    env === "private"
      ? "PRIVATE · LOCAL"
      : env === "heldout"
        ? "HELD OUT · EVALUATION"
        : "DEMO · SYNTHETIC";
  const modelLabel =
    kind === "fake"
      ? `Fake · ${runtime?.model?.model || "test"}`
      : kind === "local"
        ? `Local · ${runtime?.model?.model || "model"}`
        : `Remote · ${runtime?.model?.model || "model"}`;
  return (
      <div
        className="mt-auto rounded border px-2.5 py-2 mx-3 mb-2"
        data-testid="runtime-footnote"
        style={{ background: "var(--surface-2)", borderColor: "var(--border-subtle)" }}
      >
        <span
          className="text-[10.5px] font-medium tracking-wide"
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
        <div className="mt-0.5 text-[10.5px]" style={{ color: "var(--text-muted)" }}>
          {modelLabel}
        </div>
        {runtime?.as_of ? (
          <div className="text-[10.5px]" style={{ color: "var(--text-muted)" }}>
            data as of {observedDate(runtime.as_of) || runtime.as_of}
          </div>
        ) : null}
      </div>
  );
}
