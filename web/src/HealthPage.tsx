import { Field, Section } from "./ui";
import type { RuntimeInfo } from "./types";

export function HealthPage({
  trust,
  ingestRuns,
  completeness,
  runtime,
}: {
  trust: any;
  ingestRuns: any[];
  completeness: any;
  runtime: RuntimeInfo | null;
}) {
  const counts = completeness?.counts || {};
  return (
    <div data-testid="health-page">
      {runtime && (
        <p className="lede">
          Viewing the <strong>{runtime.environment}</strong> environment
          {runtime.synthetic ? " (synthetic)" : " (private evidence only)"}.
        </p>
      )}
      {trust && (
        <div className={`banner ${trust.ok ? "ok" : "bad"}`}>
          <div>
            <div className="banner-kicker">ingest trust</div>
            <div className="banner-title">{trust.ok ? "OK" : "NOT OK"}</div>
          </div>
          <p className="banner-q">{(trust.reasons || []).join(" ") || "Latest ingest reconciled."}</p>
        </div>
      )}
      <Section title="Source coverage">
        {Object.entries(counts).map(([k, v]) => (
          <Field key={k} label={k} value={v} />
        ))}
        {completeness?.missing_source_systems?.length ? (
          <p className="lede">Missing: {completeness.missing_source_systems.join(", ")}</p>
        ) : null}
      </Section>
      <Section title="Recent ingest runs">
        {ingestRuns.length ? ingestRuns.slice(0, 12).map((run: any) => (
          <div key={run.run_id || run.source} className="row">
            <span><strong>{run.source}</strong> {run.status}</span>
            <span className="lede" style={{ margin: 0 }}>
              loaded {run.rows_loaded ?? "—"} · rejected {run.rows_rejected ?? "—"}
            </span>
          </div>
        )) : <p className="lede">No ingest runs in this database.</p>}
      </Section>
    </div>
  );
}
