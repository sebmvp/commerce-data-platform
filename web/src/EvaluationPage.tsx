export function EvaluationPage({
  evalReport,
  compare,
  busy,
  onRerun,
  onOpenQuestion,
}: {
  evalReport: any;
  compare: any;
  busy: boolean;
  onRerun: () => void;
  onOpenQuestion: (q: string) => void;
}) {
  const lexical = compare?.lexical || compare?.rag;
  return (
    <>
      <button className="obj-link" onClick={onRerun} disabled={busy}>Re-run evaluation</button>
      {evalReport && (
        <>
          <p className="lede" style={{ marginTop: 12 }}>
            Scores the Context Engine, not an LLM. Lexical retrieval is TF-IDF, not RAG.
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
                <div className="banner-kicker">Context Engine</div>
                <div className="compare-n">{compare.engine.passed}/{compare.engine.total}</div>
              </div>
              <div>
                <div className="banner-kicker">Lexical retrieval</div>
                <div className="compare-n" data-testid="lexical-pass">{lexical.passed}/{lexical.total}</div>
                <p className="lede" style={{ margin: "4px 0 0" }}>TF-IDF over serialized rows. Not RAG.</p>
              </div>
            </div>
          )}
          {evalReport.cases.map((c: any) => (
            <div
              key={c.id}
              className="row"
              data-testid={`eval-case-${c.id}`}
              onClick={() => onOpenQuestion(c.question)}
            >
              <span>
                <span className={c.passed ? "pass" : c.skipped ? "skip" : "fail"}>
                  {c.passed ? "PASS" : c.skipped ? "SKIP" : "FAIL"}
                </span>{" "}
                {c.id} {c.question}
              </span>
            </div>
          ))}
        </>
      )}
    </>
  );
}
