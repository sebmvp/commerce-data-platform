import { Field, Section } from "./ui";
import type { CompletenessReport, IngestRun, RuntimeInfo, TrustReport } from "./types";

export function HealthPage({
  trust,
  ingestRuns,
  completeness,
  runtime,
}: {
  trust: TrustReport | null;
  ingestRuns: IngestRun[];
  completeness: CompletenessReport | null;
  runtime: RuntimeInfo | null;
}) {
  const counts = completeness?.counts || {};
  const coverage = completeness?.coverage || [];
  const latest = completeness?.latest_ingest;
  return (
    <div data-testid="health-page">
      {runtime && (
        <p className="lede">
          Viewing the <strong>{runtime.environment}</strong> environment
          {runtime.synthetic ? " (synthetic world)" : " (private evidence only)"}.
          {completeness?.world_as_of ? ` World as-of ${completeness.world_as_of}.` : ""}
          {completeness?.seed != null ? ` Seed ${completeness.seed}.` : ""}
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
      {latest && (
        <Section title="Latest ingest">
          <Field label="source" value={latest.source} />
          <Field label="status" value={latest.status} />
          <Field label="read" value={latest.read} />
          <Field label="loaded" value={latest.loaded} />
          <Field label="rejected" value={latest.rejected} />
        </Section>
      )}
      <Section title="Source coverage">
        {coverage.length
          ? coverage.map((row) => (
              <div key={row.category} className="row">
                <span><strong>{row.category}</strong> {row.status}</span>
                <span className="lede" style={{ margin: 0 }}>{row.detail}</span>
              </div>
            ))
          : Object.entries(counts).map(([k, v]) => (
              <Field key={k} label={k} value={v} />
            ))}
        {completeness?.missing_source_systems?.length ? (
          <p className="lede">Missing: {completeness.missing_source_systems.join(", ")}</p>
        ) : null}
      </Section>
      <Section title="Recent ingest runs">
        {ingestRuns.length ? ingestRuns.slice(0, 12).map((run) => (
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
