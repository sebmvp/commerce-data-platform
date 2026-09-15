import { Field, Section, StatusChip } from "@/components/primitives";
import { ErrorNote } from "@/App";
import { observedDate } from "@/lib/format";
import { useCompleteness, useIngestRuns, useRuntime, useTrust } from "@/lib/api";

export function DataHealthPage() {
  const runtime = useRuntime();
  const trust = useTrust();
  const runs = useIngestRuns();
  const completeness = useCompleteness();

  const counts = completeness.data?.counts || {};
  const coverage = completeness.data?.coverage || [];
  const latest = completeness.data?.latest_ingest;
  const env = runtime.data?.environment || "demo";

  return (
    <div className="mx-auto max-w-5xl px-5 py-4" data-testid="health-page">
      <header className="mb-4">
        <h1 className="text-[17px] font-semibold tracking-tight">Data Health</h1>
        <p className="mt-0.5 text-[13px]" style={{ color: "var(--text-muted)" }}>
          Viewing the <span style={{ color: "var(--text-secondary)" }}>{env}</span> environment
          {runtime.data?.synthetic ? " (synthetic world)" : " (private evidence only)"}
          {completeness.data?.world_as_of
            ? ` · world as of ${observedDate(completeness.data.world_as_of) || completeness.data.world_as_of}`
            : ""}
          {completeness.data?.seed != null ? ` · seed ${completeness.data.seed}` : ""}
        </p>
      </header>

      {trust.isError || runs.isError || completeness.isError ? (
        <ErrorNote error={trust.error || runs.error || completeness.error} />
      ) : null}

      {trust.isPending ? (
        <div className="h-16 animate-pulse rounded border" style={{ background: "var(--surface-2)", borderColor: "var(--border-subtle)" }} />
      ) : trust.data ? (
        <div
          className="mb-4 flex items-center justify-between gap-4 rounded border px-4 py-3"
          data-testid="trust-banner"
          style={{
            background: "var(--surface-1)",
            borderColor: trust.data.ok ? "#14532d" : "#7f1d1d",
          }}
        >
          <div>
            <div className="section-label">Ingest trust</div>
            <div
              className="text-[19px] font-semibold tracking-tight"
              style={{ color: trust.data.ok ? "var(--success)" : "var(--danger)" }}
            >
              {trust.data.ok ? "OK" : "NOT OK"}
            </div>
          </div>
          <p className="max-w-[52ch] text-right text-[12.5px]" style={{ color: "var(--text-muted)" }}>
            {(trust.data.reasons || []).join(" ") || "Latest ingest reconciled."}
          </p>
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-5 max-[900px]:grid-cols-1">
        <div className="space-y-5">
          {latest ? (
            <Section title="Latest ingest" tone="inset">
              <Field label="source" value={String(latest.source || "—")} />
              <Field label="status" value={String(latest.status || "—")} />
              <Field label="read" value={String(latest.read ?? "—")} />
              <Field label="loaded" value={String(latest.loaded ?? "—")} />
              <Field label="rejected" value={String(latest.rejected ?? "—")} />
            </Section>
          ) : null}

          <Section title="Source coverage" testId="coverage">
            {completeness.isPending ? (
              <div className="h-20 animate-pulse rounded" style={{ background: "var(--surface-2)" }} />
            ) : coverage.length ? (
              coverage.map((row) => (
                <div
                  key={row.category}
                  className="flex items-baseline justify-between gap-3 border-b py-1.5 last:border-0"
                  style={{ borderColor: "var(--border-subtle)" }}
                >
                  <span className="text-[13.5px]" style={{ color: "var(--text-primary)" }}>
                    {row.category}{" "}
                    <StatusChip tone={row.status === "ok" ? "ok" : row.status === "missing" ? "warn" : "muted"}>
                      {row.status}
                    </StatusChip>
                  </span>
                  <span className="max-w-[46ch] text-right text-[12px]" style={{ color: "var(--text-muted)" }}>
                    {row.detail}
                  </span>
                </div>
              ))
            ) : Object.keys(counts).length ? (
              Object.entries(counts).map(([k, v]) => <Field key={k} label={human(k)} value={v} />)
            ) : (
              <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                No coverage data for this database.
              </p>
            )}
            {completeness.data?.missing_source_systems?.length ? (
              <p className="mt-1.5 text-[12px]" style={{ color: "var(--warning)" }}>
                Missing sources: {completeness.data.missing_source_systems.join(", ")}
              </p>
            ) : null}
          </Section>
        </div>

        <div>
          <Section title="Recent ingest runs" testId="ingest-runs" tone="inset">
            {runs.isPending ? (
              <div className="h-24 animate-pulse rounded" style={{ background: "var(--surface-2)" }} />
            ) : (runs.data || []).length ? (
              (runs.data || []).slice(0, 12).map((run, i) => (
                <div
                  key={run.run_id || `${run.source}-${i}`}
                  className="flex items-baseline justify-between gap-3 border-b py-1.5 last:border-0"
                  style={{ borderColor: "var(--border-subtle)" }}
                >
                  <span className="text-[13.5px]" style={{ color: "var(--text-primary)" }}>
                    {run.source}{" "}
                    <StatusChip tone={run.status === "success" ? "ok" : "bad"}>{run.status}</StatusChip>
                  </span>
                  <span className="tabular text-[12px]" style={{ color: "var(--text-muted)" }}>
                    loaded {run.rows_loaded ?? "—"} · rejected {run.rows_rejected ?? "—"}
                    {run.started_at ? ` · ${observedDate(run.started_at) || ""}` : ""}
                  </span>
                </div>
              ))
            ) : (
              <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                No ingest runs in this database — run <span className="mono">cdp build --sample</span> to seed the demo world.
              </p>
            )}
          </Section>
        </div>
      </div>
    </div>
  );
}

function human(raw: string): string {
  return raw.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
