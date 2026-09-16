import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { ErrorNote } from "@/App";
import { useEvalLayers } from "@/lib/api";

/**
 * System verification — layered, no combined accuracy number. Layer results
 * first; the per-question detail is deliberate progressive disclosure.
 */
export function EvaluationPage() {
  const { core, compare, answers, plan, librarian, loading, error } = useEvalLayers();
  const [showCases, setShowCases] = useState(false);

  const engine = compare.data?.engine;
  const lexical = compare.data?.lexical;
  const summary = core.data;

  const coreLayers = [
    { label: "Context assembly", value: engine ? `${engine.passed}/${engine.total}` : summary ? `${summary.passed}/${summary.total}` : "—", note: "Typed bundle per question." },
    { label: "Question planning", value: plan.data ? `${plan.data.passed}/${plan.data.total}` : "—", note: "Capability mapping." },
    { label: "Grounding", value: answers.data ? `${answers.data.passed}/${answers.data.total}` : "—", note: "Citation validity, fail-closed." },
    { label: "Librarian tasks", value: librarian.data ? `${librarian.data.passed}/${librarian.data.total}` : "—", note: "Registered-tool loop." },
  ];

  return (
    <div className="mx-auto max-w-5xl px-6 py-5" data-testid="eval-page">
      <header className="mb-4">
        <h1 className="text-[18px] font-semibold tracking-tight">System verification</h1>
        <p className="mt-0.5 max-w-[70ch] text-[13px]" style={{ color: "var(--text-muted)" }}>
          Layers are verified separately — there is no combined accuracy number.
        </p>
      </header>

      {error ? <ErrorNote error={error} /> : null}

      {loading && !summary ? (
        <div className="grid grid-cols-2 gap-3 max-[600px]:grid-cols-1">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-14 animate-pulse rounded border" style={{ background: "var(--surface-2)", borderColor: "var(--border-subtle)" }} />
          ))}
        </div>
      ) : null}

      {summary ? (
        <>
          <div data-testid="eval-summary" className="mb-5">
            {coreLayers.map((layer) => (
              <div
                key={layer.label}
                className="flex items-baseline justify-between gap-4 border-b py-2 last:border-0"
                style={{ borderColor: "var(--border-subtle)" }}
              >
                <span className="text-[13.5px] font-medium" style={{ color: "var(--text-primary)" }}>
                  {layer.label}
                </span>
                <span className="flex items-baseline gap-3">
                  <span className="tabular text-[15px] font-semibold" style={{ color: "var(--text-primary)" }}>
                    {layer.value}
                  </span>
                  <span className="text-[12px]" style={{ color: "var(--text-muted)" }}>
                    {layer.note}
                  </span>
                </span>
              </div>
            ))}
          </div>

          {/* Lexical baseline — visually quieter, comparison only */}
          <div
            className="mb-5 rounded border px-3 py-2.5"
            data-testid="lexical"
            style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}
          >
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
                Lexical baseline{" "}
                <span className="tabular" style={{ color: "var(--text-muted)" }}>
                  {lexical && lexical.passed != null ? `${lexical.passed}/${lexical.total}` : "—"}
                </span>
              </span>
              <span className="text-[12px]" style={{ color: "var(--text-muted)" }}>
                Naive TF-IDF retrieval over serialized rows — comparison only.
                The engine must beat it; it is not the product.
              </span>
            </div>
          </div>

          {/* Progressive disclosure: cases only after click */}
          <button
            type="button"
            data-testid="toggle-cases"
            onClick={() => setShowCases((v) => !v)}
            className="rounded border px-3 py-1.5 text-[13px] font-medium focus-ring"
            style={{ borderColor: "var(--border-subtle)", color: "var(--text-secondary)" }}
          >
            {showCases ? "Hide detailed cases" : "View detailed cases"}
          </button>

          {showCases ? (
            <div className="mt-4">
              <div className="section-label mb-1.5">Per-question context assembly</div>
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
                      color: c.passed
                        ? "var(--success)"
                        : c.skipped
                          ? "var(--text-muted)"
                          : "var(--danger)",
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
          ) : null}
        </>
      ) : null}
    </div>
  );
}
