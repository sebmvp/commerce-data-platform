import { Link } from "@tanstack/react-router";
import { ErrorNote } from "@/App";
import { useEvalLayers } from "@/lib/api";

export function EvaluationPage() {
  const { core, compare, answers, plan, librarian, loading, error } = useEvalLayers();

  const engine = compare.data?.engine;
  const lexical = compare.data?.lexical;
  const summary = core.data;

  return (
    <div className="mx-auto max-w-5xl px-5 py-4" data-testid="eval-page">
      <header className="mb-4 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-[17px] font-semibold tracking-tight">Evaluation</h1>
          <p className="mt-0.5 max-w-[70ch] text-[13px]" style={{ color: "var(--text-muted)" }}>
            Layers are reported separately — there is no combined “AI accuracy” number.
            Context assembly scores the engine. Planning scores capability mapping.
            Grounding scores FakeProvider citations. Librarian scores the registered-tool loop.
          </p>
        </div>
      </header>

      {error ? <ErrorNote error={error} /> : null}

      {loading && !summary ? (
        <div className="grid grid-cols-3 gap-3 max-[600px]:grid-cols-1">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-16 animate-pulse rounded border" style={{ background: "var(--surface-2)", borderColor: "var(--border-subtle)" }} />
          ))}
        </div>
      ) : null}

      {summary ? (
        <>
          <div className="mb-4 flex gap-6 border-y py-2.5" style={{ borderColor: "var(--border-subtle)" }} data-testid="eval-summary">
            <Stat label="total" value={summary.total} />
            <Stat label="pass" value={summary.passed} tone="var(--success)" testId="eval-pass" />
            <Stat label="fail" value={summary.failed} tone={summary.failed ? "var(--danger)" : "var(--text-muted)"} testId="eval-fail" />
            <Stat label="skip" value={summary.skipped} tone="var(--text-muted)" testId="eval-skip" />
            <span className="ml-auto self-center text-[12px]" style={{ color: "var(--text-muted)" }}>
              gold context-assembly ids
            </span>
          </div>

          <div className="grid grid-cols-3 gap-3 max-[900px]:grid-cols-1" data-testid="eval-layers">
            <LayerCard
              title="Context assembly"
              value={engine ? `${engine.passed}/${engine.total}` : summary ? `${summary.passed}/${summary.total}` : "—"}
              note="Typed ContextBundle per question."
              testId="eval-compare"
            />
            <LayerCard
              title="Lexical retrieval"
              value={lexical && (lexical.passed != null) ? `${lexical.passed}/${lexical.total}` : "—"}
              note="TF-IDF over serialized rows. Not RAG — it is the naive baseline the engine must beat."
              tone={lexical && (lexical.passed ?? 0) < (lexical.total ?? 1) ? "var(--warning)" : undefined}
              testId="lexical"
            />
            <LayerCard
              title="Question / tool planning"
              value={plan.data ? `${plan.data.passed}/${plan.data.total}` : "—"}
              note="Deterministic intent mapping."
            />
            <LayerCard
              title="Grounding validity"
              value={answers.data ? `${answers.data.passed}/${answers.data.total}` : "—"}
              note="FakeProvider copilot contract. Not an LLM judge."
            />
            <LayerCard
              title="Librarian task success"
              value={librarian.data ? `${librarian.data.passed}/${librarian.data.total}` : "—"}
              note="Registered-tool loop, abstention, citation validity."
            />
          </div>

          <div className="mt-5">
            <div className="section-label mb-1.5">Per-question context assembly</div>
            <div>
              {(summary.cases || []).map((c) => (
                <Link
                  key={String(c.id)}
                  to="/librarian"
                  search={{ q: String(c.question || "") }}
                  className="flex items-baseline gap-3 border-b py-1.5 last:border-0 focus-ring"
                  style={{ borderColor: "var(--border-subtle)" }}
                  data-testid={`eval-case-${c.id}`}
                >
                  <span
                    className="w-10 shrink-0 text-[11.5px] font-medium"
                    style={{
                      color: c.passed ? "var(--success)" : c.skipped ? "var(--text-muted)" : "var(--danger)",
                    }}
                  >
                    {c.passed ? "PASS" : c.skipped ? "SKIP" : "FAIL"}
                  </span>
                  <span className="text-[13.5px]" style={{ color: "var(--text-secondary)" }}>
                    {String(c.question || "")}
                  </span>
                </Link>
              ))}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
  testId,
}: {
  label: string;
  value: unknown;
  tone?: string;
  testId?: string;
}) {
  return (
    <div data-testid={testId}>
      <div className="text-[11px] uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
        {label}
      </div>
      <div className="tabular text-[20px] font-semibold" style={{ color: tone || "var(--text-primary)" }}>
        {value == null ? "—" : String(value)}
      </div>
    </div>
  );
}

function LayerCard({
  title,
  value,
  note,
  tone,
  testId,
}: {
  title: string;
  value: string;
  note?: string;
  tone?: string;
  testId?: string;
}) {
  return (
    <div
      className="rounded border p-3"
      data-testid={testId}
      style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}
    >
      <div className="section-label">{title}</div>
      <div className="tabular mt-0.5 text-[20px] font-semibold tracking-tight" style={{ color: tone || "var(--text-primary)" }}>
        {value}
      </div>
      {note ? (
        <p className="mt-1 text-[12px]" style={{ color: "var(--text-muted)" }}>
          {note}
        </p>
      ) : null}
    </div>
  );
}
