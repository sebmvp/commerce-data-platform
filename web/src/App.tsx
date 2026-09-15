import { type ReactNode, useEffect } from "react";
import { useRouterState } from "@tanstack/react-router";
import { useRuntime } from "@/lib/api";
import { AppShell } from "@/components/AppShell";

export function App({ children }: { children: ReactNode }) {
  const runtime = useRuntime();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  // Keep the shell's runtime footnote fresh across route changes; one fetch
  // per session with a 60s staleTime means this costs almost nothing.
  useEffect(() => {
    void runtime.refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  return <AppShell>{children}</AppShell>;
}

export function usePathSku(): string | null {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const match = pathname.match(/\/(inventory|librarian)\/([^/]+)/);
  return match ? decodeURIComponent(match[2]) : null;
}

export function LoadingDots({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[13px]" style={{ color: "var(--text-muted)" }}>
      <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full" style={{ background: "var(--accent-support)" }} />
      {label}
    </span>
  );
}

export function ErrorNote({ error, retry }: { error: unknown; retry?: () => void }) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div
      className="rounded border px-3 py-2 text-[13.5px]"
      style={{ borderColor: "#7f1d1d", background: "#1a1014", color: "var(--danger)" }}
      data-testid="error-state"
    >
      <div className="font-medium">Request failed</div>
      <div className="mt-0.5 text-[12.5px]" style={{ color: "var(--text-secondary)" }}>
        {message}
      </div>
      {retry ? (
        <button
          className="mt-1.5 text-[12.5px] underline focus-ring"
          onClick={retry}
          style={{ color: "var(--text-secondary)" }}
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}
