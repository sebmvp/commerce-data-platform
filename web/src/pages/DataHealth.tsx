import { StatusChip } from "@/components/primitives";
import { ErrorNote } from "@/App";
import { coverageTone, observedDate } from "@/lib/format";
import { useCompleteness, useIngestRuns, useRuntime, useTrust } from "@/lib/api";

/**
 * Data Health — can I trust the current state? Trust banner and coverage
 * first; detailed ingest diagnostics behind disclosure.
 */
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
    <div className="mx-auto max-w-5xl px-6 py-5" data-testid="health-page">
      <header className="mb-4">
        <h1 className="text-[18px] font-semibold tracking-tight">Data Health</h1>
        <p className="tabular mt-0.5 text-[12.5px]" style={{ color: "var(--text-muted)" }}>
          {env === "private" ? "PRIVATE · LOCAL" : env === "heldout" ? "HELD OUT · EVALUATION" : "DEMO · SYNTHETIC"}
          {completeness.data?.world_as_of
            ? ` · world as of ${observedDate(completeness.data.world_as_of) || completeness.data.world_as_of}`
            : ""}
        </p>
      </header>

      {trust.isError || runs.isError || completeness.isError ? (
        <ErrorNote error={trust.error || runs.error || completeness.error} />
      ) : null}

      {/* Can I trust this? */}
      {trust.isPending ? (
        <div className="mb-4 h-16 animate-pulse rounded border" style={{ background: "var(--surface-2)", borderColor: "var(--border-subtle)" }} />
      ) : trust.data ? (
        <div
          className="mb-5 flex items-start justify-between gap-4 rounded border px-4 py-3"
          data-testid="trust-banner"
          style={{
            background: "var(--surface-1)",
            borderColor: trust.data.ok ? "#14532d" : "#7f1d1d",
          }}
        >
          <div>
            <div className="section-label">Can I trust this?</div>
            <div
              className="text-[19px] font-semibold tracking-tight"
              style={{ color: trust.data.ok ? "var(--success)" : "var(--danger)" }}
            >
              {trust.data.ok ? "OK" : "NOT OK"}
            </div>
          </div>
          <p className="max-w-[52ch] text-right text-[12.5px]" style={{ color: "var(--text-muted)" }}>
            {(trust.data.reasons || []).join(" ") ||
              "Latest ingest reconciled."}
          </p>
        </div>
      ) : null}

      {/* Coverage */}
      <section data-testid="coverage">
        <div className="section-label mb-1.5">Source coverage</div>
        {completeness.isPending ? (
          <div className="h-20 animate-pulse rounded" style={{ background: "var(--surface-2)" }} />
        ) : coverage.length ? (
          <div>
            {coverage.map((row, i) => (
              <div
                key={`${row.category}-${i}`}
                className="flex items-baseline justify-between gap-3 border-b py-1.5 last:border-0"
                style={{ borderColor: "var(--border-subtle)" }}
              >
                <span className="text-[13.5px]" style={{ color: "var(--text-primary)" }}>
                  {row.category}{" "}
                  <StatusChip tone={coverageTone(row.status)}>
                    {String(row.status || "").toLowerCase() === "available" ? "available" : String(row.status || "").toLowerCase()}
                  </StatusChip>
                </span>
                <span className="max-w-[46ch] text-right text-[12px]" style={{ color: "var(--text-muted)" }}>
                  {row.detail}
                </span>
              </div>
            ))}
          </div>
        ) : counts && Object.keys(counts).length ? (
          <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
            {Object.entries(counts).map(([k, v]) => `${v} ${k.replace(/_/g, " ")}`).join(" · ")}
          </p>
        ) : (
          <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
            No coverage data for this database.
          </p>
        )}
        {!!completeness.data?.missing_source_systems?.length ? (
          <p className="mt-1.5 text-[12.5px]" style={{ color: "var(--warning)" }}>
            Missing sources: {completeness.data.missing_source_systems.join(", ")}
          </p>
        ) : null}
      </section>

      {/* Latest ingest — one block */}
      {latest ? (
        <section className="mt-5">
          <div className="section-label mb-1.5">Latest ingest</div>
          <p className="tabular text-[13px]" style={{ color: "var(--text-secondary)" }}>
            {String(latest.source || "").replace("ops.", "")}{" "}
            loaded {String(latest.loaded ?? "—")} · rejected {String(latest.rejected ?? "—")}
            {latest.finished_at
              ? ` · ${observedDate(String(latest.finished_at)) || String(latest.finished_at)}`
              : ""}
          </p>
        </section>
      ) : null}

      {/* Detailed diagnostics behind disclosure */}
      <details className="mt-5" data-testid="ingest-runs-details">
        <summary className="cursor-pointer text-[13px] focus-ring" style={{ color: "var(--text-muted)" }}>
          Recent ingest runs
        </summary>
        <div className="mt-2" data-testid="ingest-runs">
          {(runs.data || []).length ? (
            (runs.data || []).slice(0, 12).map((run, i) => (
              <div
                key={run.run_id || `${run.source}-${i}`}
                className="flex items-baseline justify-between gap-3 border-b py-1.5 last:border-0"
                style={{ borderColor: "var(--border-subtle)" }}
              >
                <span className="text-[13px]" style={{ color: "var(--text-primary)" }}>
                  {String(run.source || "").replace("ops.", "")}{" "}
                  <StatusChip tone={run.status === "success" ? "ok" : "bad"}>
                    {run.status}
                  </StatusChip>
                </span>
                <span className="tabular text-[12px]" style={{ color: "var(--text-muted)" }}>
                  loaded {run.rows_loaded ?? "—"} · rejected {run.rows_rejected ?? "—"}
                  {run.started_at ? ` · ${observedDate(run.started_at) || ""}` : ""}
                </span>
              </div>
            ))
          ) : (
            <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
              No ingest runs in this database — run <span className="mono">make seed</span> to seed the demo world.
            </p>
          )}
        </div>
      </details>
    </div>
  );
}
