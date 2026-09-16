import { StatusChip } from "@/components/primitives";
import { ErrorNote } from "@/App";
import { coverageTone, observedDate } from "@/lib/format";
import { useCompleteness, useIngestRuns, useRuntime } from "@/lib/api";

/**
 * Sources — where canonical state comes from, honestly. The Data Steward
 * is CLI-only today; the UI discloses that role rather than inventing an
 * onboarding wizard it cannot back.
 */
export function SourcesPage() {
  const runtime = useRuntime();
  const completeness = useCompleteness();
  const runs = useIngestRuns();

  const counts = completeness.data?.counts || {};
  const coverage = completeness.data?.coverage || [];
  const latest = completeness.data?.latest_ingest;
  const env = runtime.data?.environment || "demo";
  const isSynthetic = runtime.data?.synthetic ?? true;

  const SOURCE_CLASSES: Array<{ label: string; countKey: string; use: string }> = [
    { label: "Items", countKey: "items", use: "Catalog identity, lifecycle, sourcing cost" },
    { label: "Listings", countKey: "listings", use: "Channel state and ask prices" },
    { label: "Orders", countKey: "orders", use: "Realized sales and revenue" },
    { label: "Engagement", countKey: "engagement_snapshots", use: "Watchers, views, offers over time" },
    { label: "Notes", countKey: "notes", use: "Condition and operator callouts" },
    { label: "Sandbox actions", countKey: "sandbox_actions", use: "Approved internal repricing history" },
  ];

  return (
    <div className="mx-auto max-w-5xl px-6 py-5" data-testid="sources-page">
      <header className="mb-4">
        <h1 className="text-[18px] font-semibold tracking-tight">Sources</h1>
        <p className="mt-0.5 max-w-[70ch] text-[13px]" style={{ color: "var(--text-muted)" }}>
          Where canonical state comes from. The Data Steward proposes source
          contracts; deterministic ingest remains the only writer.
        </p>
        <p className="tabular mt-1 text-[12.5px]" style={{ color: "var(--text-muted)" }}>
          {env === "private" ? "PRIVATE · LOCAL" : isSynthetic ? "synthetic world" : env}
          {completeness.data?.world_as_of
            ? ` · world as of ${observedDate(completeness.data.world_as_of) || completeness.data.world_as_of}`
            : ""}
        </p>
      </header>

      {completeness.isError || runs.isError ? (
        <ErrorNote error={completeness.error || runs.error} />
      ) : null}

      {completeness.isPending ? (
        <div className="h-32 animate-pulse rounded border" style={{ background: "var(--surface-2)", borderColor: "var(--border-subtle)" }} />
      ) : (
        <>
          <div
            className="mb-4 flex items-center gap-2 rounded border px-4 py-2.5"
            data-testid="sources-trust"
            style={{
              background: "var(--surface-1)",
              borderColor: latest?.status === "success" ? "#14532d" : "#7f1d1d",
            }}
          >
            <StatusChip tone={latest?.status === "success" ? "ok" : "bad"}>
              {latest ? "trust " + (latest.status === "success" ? "OK" : "NOT OK") : "no ingest"}
            </StatusChip>
            <span className="tabular text-[12.5px]" style={{ color: "var(--text-muted)" }}>
              {latest
                ? `latest ingest ${String(latest.source || "")} loaded ${latest.loaded ?? "—"} · rejected ${latest.rejected ?? "—"} · ${observedDate(String(latest.finished_at || "")) || "—"}`
                : "no ingest recorded in this database"}
            </span>
          </div>

          <div className="mb-2 section-label">What feeds this business</div>
          <div
            data-testid="sources-table"
            className="overflow-hidden rounded border"
            style={{ borderColor: "var(--border-subtle)" }}
          >
            <table className="w-full border-collapse text-left">
              <thead style={{ background: "var(--surface-2)" }}>
                <tr>
                  {["Source", "Volume", "Used for", "State"].map((h) => (
                    <th
                      key={h}
                      className="border-b px-3 py-2 text-[11.5px] font-medium uppercase tracking-wide"
                      style={{ borderColor: "var(--border-subtle)", color: "var(--text-muted)" }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {SOURCE_CLASSES.map((cls) => {
                  const count = counts[cls.countKey];
                  const cov = coverage.find(
                    (c) =>
                      String(c.category || "")
                        .toLowerCase()
                        .startsWith(cls.label.toLowerCase().split(" ")[0].toLowerCase()),
                  );
                  const state = cls.countKey === "items" || count == null ? cov?.status || "AVAILABLE" : cov?.status || (count > 0 ? "AVAILABLE" : "MISSING");
                  return (
                    <tr key={cls.label} className="border-b" style={{ borderColor: "var(--border-subtle)" }}>
                      <td className="px-3 py-2 text-[13.5px]" style={{ color: "var(--text-primary)" }}>
                        {cls.label}
                      </td>
                      <td className="tabular px-3 py-2 text-[13px]" style={{ color: "var(--text-secondary)" }}>
                        {count != null ? `${count} ${cls.label.toLowerCase()}` : "—"}
                      </td>
                      <td className="px-3 py-2 text-[12.5px]" style={{ color: "var(--text-muted)" }}>
                        {cls.use}
                      </td>
                      <td className="px-3 py-2">
                        <StatusChip tone={coverageTone(state)}>
                          {state === "AVAILABLE" ? "healthy" : state.toLowerCase()}
                        </StatusChip>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {!!completeness.data?.missing_source_systems?.length ? (
            <p className="mt-2 text-[12.5px]" style={{ color: "var(--warning)" }}>
              Missing source classes: {completeness.data.missing_source_systems.join(", ")} — canonical rows cannot exist for records that were never loaded.
            </p>
          ) : null}

          {isSynthetic ? (
            <p className="mt-2 text-[12.5px]" style={{ color: "var(--text-muted)" }}>
              This environment is synthetic; volumes show what the demo world loaded, not a real marketplace.
            </p>
          ) : null}

          {/* Data Steward: honest disclosure, no fake wizard */}
          <details className="mt-5" data-testid="steward-disclosure">
            <summary className="cursor-pointer text-[13px] focus-ring" style={{ color: "var(--text-secondary)" }}>
              Add a source — how onboarding actually works
            </summary>
            <div
              className="mt-2 rounded border px-4 py-3 text-[13px]"
              style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}
            >
              <p className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
                The Data Steward profiles a file and proposes a source contract.
                Onboarding is a developer workflow (CLI) today — no file upload
                exists in this UI, and canonical writes stay deterministic.
              </p>
              <ol className="m-0 mt-2 list-decimal space-y-1 pl-5 text-[12.5px]" style={{ color: "var(--text-muted)" }}>
                <li>
                  Profile — <span className="mono">cdp onboard profile &lt;path&gt;</span>
                </li>
                <li>
                  The Steward proposes a PROPOSED contract (writes no canonical rows)
                </li>
                <li>
                  Human review — <span className="mono">cdp onboard review &lt;proposal.json&gt;</span>
                </li>
                <li>
                  Deterministic ingest — <span className="mono">cdp ingest</span> /{" "}
                  <span className="mono">make ingest-private</span>
                </li>
              </ol>
            </div>
          </details>

          <details className="mt-3" data-testid="ingest-runs-details">
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
                  No ingest runs recorded.
                </p>
              )}
            </div>
          </details>
        </>
      )}
    </div>
  );
}
