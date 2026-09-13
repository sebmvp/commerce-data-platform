import type { EvalLayerReport } from "./types";

export function EvaluationPage({
  evalReport,
  compare,
  answers,
  planEval,
  analystEval,
  busy,
  onRerun,
  onOpenQuestion,
}: {
  evalReport: EvalLayerReport | null;
  compare: EvalLayerReport | null;
  answers: EvalLayerReport | null;
  planEval: EvalLayerReport | null;
  analystEval: EvalLayerReport | null;
  busy: boolean;
  onRerun: () => void;
  onOpenQuestion: (q: string) => void;
}) {
  const lexical = compare?.lexical;
  return (
    <>
      <button className="obj-link" onClick={onRerun} disabled={busy}>Re-run evaluation</button>
      {evalReport && (
        <>
          <p className="lede" style={{ marginTop: 12 }}>
            Layers are reported separately. There is no combined “AI accuracy” number.
            Context assembly scores the engine. Planning scores capability mapping.
            Grounding scores FakeProvider citations. Analyst scores the registered-tool loop.
          </p>
          <div className="eval-bar" data-testid="eval-summary">
            <span>TOTAL <strong data-testid="eval-total">{evalReport.total}</strong></span>
            <span className="pass">PASS <strong data-testid="eval-pass">{evalReport.passed}</strong></span>
            <span className={evalReport.failed ? "fail" : ""}>FAIL <strong data-testid="eval-fail">{evalReport.failed}</strong></span>
            <span className={evalReport.skipped ? "fail" : "skip"}>SKIP <strong data-testid="eval-skip">{evalReport.skipped}</strong></span>
          </div>
          {lexical && (
            <div className="compare-bar" data-testid="eval-compare">
              <div>
                <div className="banner-kicker">Context assembly</div>
                <div className="compare-n">{compare.engine?.passed}/{compare.engine?.total}</div>
              </div>
              <div>
                <div className="banner-kicker">Lexical retrieval</div>
                <div className="compare-n" data-testid="lexical-pass">{lexical.passed}/{lexical.total}</div>
                <p className="lede" style={{ margin: "4px 0 0" }}>TF-IDF over serialized rows. Not RAG.</p>
              </div>
            </div>
          )}
          <div className="compare-bar" data-testid="eval-layers">
            {planEval && (
              <div data-testid="eval-plan">
                <div className="banner-kicker">Question / tool planning</div>
                <div className="compare-n">{planEval.passed}/{planEval.total}</div>
              </div>
            )}
            {answers && (
              <div data-testid="eval-answers">
                <div className="banner-kicker">Grounding validity</div>
                <div className="compare-n">{answers.passed}/{answers.total}</div>
                <p className="lede" style={{ margin: "4px 0 0" }}>
                  FakeProvider copilot contract. Not an LLM judge.
                </p>
              </div>
            )}
            {analystEval && (
              <div data-testid="eval-analyst">
                <div className="banner-kicker">Agent task success</div>
                <div className="compare-n">{analystEval.passed}/{analystEval.total}</div>
              </div>
            )}
          </div>
          {(evalReport.cases || []).map((c) => (
            <div
              key={String(c.id)}
              className="row"
              data-testid={`eval-case-${c.id}`}
              onClick={() => onOpenQuestion(String(c.question))}
            >
              <span>
                <span className={c.passed ? "pass" : c.skipped ? "skip" : "fail"}>
                  {c.passed ? "PASS" : c.skipped ? "SKIP" : "FAIL"}
                </span>{" "}
                {String(c.id || "")} {String(c.question || "")}
              </span>
            </div>
          ))}
        </>
      )}
    </>
  );
}
