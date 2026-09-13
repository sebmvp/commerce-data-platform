import { useState } from "react";
import { RelationshipMap } from "./RelationshipMap";
import type {
  AnalystResponse,
  ContextBundle,
  ContextObject,
  EvidenceUnit,
} from "./types";
import { Field, itemLabel, Section } from "./ui";

const SAMPLES = [
  "Should I reprice j4-military-s?",
  "Should I reprice stone-cargo-l?",
  "What was the active listing state for j4-military-s two weeks ago?",
  "Which listings have strong attention but weak offer conversion?",
  "What should I focus on today?",
];

function formatEvidenceValue(value: unknown): string | null {
  if (value == null || value === "") return null;
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "number") {
    if (value > 0 && value < 1) return `${(value * 100).toFixed(1)}%`;
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  if (typeof value === "object") return null;
  return String(value);
}

function citedUnits(answer: AnalystResponse | null, bundle: ContextBundle | null): EvidenceUnit[] {
  const units = [
    ...(answer?.evidence?.evidence_units || []),
    ...(bundle?.evidence_units || []),
  ];
  const byRef = new Map(units.map((unit) => [unit.ref, unit]));
  return (answer?.evidence_refs || []).map(
    (ref) => byRef.get(ref) || { ref, kind: "unknown", label: ref },
  );
}

export function ContextPage({
  question,
  setQuestion,
  bundle,
  answer,
  busy,
  onAsk,
  onOpenObject,
}: {
  question: string;
  setQuestion: (q: string) => void;
  bundle: ContextBundle | null;
  answer: AnalystResponse | null;
  busy: boolean;
  onAsk: (q: string) => void;
  onOpenObject: (obj: ContextObject) => void;
}) {
  const [showRaw, setShowRaw] = useState(false);
  const objects = bundle?.objects ?? [];
  const facts = bundle?.facts ?? {};
  const provenance = bundle?.provenance || {};
  const requirements = bundle?.requirements || [];
  const fake = answer?.provider === "fake" || answer?.provider_kind === "fake";
  const cited = citedUnits(answer, bundle);

  return (
    <>
      <form
        className="ask"
        onSubmit={(e) => {
          e.preventDefault();
          onAsk(question);
        }}
      >
        <input
          data-testid="question-input"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask an operational question"
        />
        <button type="submit" disabled={busy}>Ask Analyst</button>
      </form>
      <div className="samples">
        {SAMPLES.map((s) => (
          <button key={s} className="chip" onClick={() => { setQuestion(s); onAsk(s); }}>
            {s}
          </button>
        ))}
      </div>
      {bundle && (
        <>
          <div className={`banner ${bundle.sufficient ? "ok" : "bad"}`} data-testid="sufficiency">
            <div>
              <div className="banner-kicker" data-testid="interpreted-plan">
                {(answer?.plan?.capability || bundle.intent)
                  + (answer?.plan?.subject ? ` · ${answer.plan.subject}` : "")
                  + (bundle.as_of ? ` · as of ${bundle.as_of}` : "")}
              </div>
              <div className="banner-title">{bundle.sufficient ? "SUFFICIENT" : "INSUFFICIENT"}</div>
            </div>
            <p className="banner-q" data-testid="assembled-question">{bundle.question}</p>
          </div>
          {answer && (
            <section
              className={`missing-panel ${
                answer.grounding_status === "grounded"
                  ? "ok-panel"
                  : answer.grounding_status === "invalid"
                    ? "invalid-panel"
                    : ""
              }`}
              data-testid="grounded-output"
            >
              <h2 data-testid="grounded-answer">
                {answer.grounding_status === "invalid"
                  ? "INVALID MODEL OUTPUT"
                  : answer.abstained
                    ? "ABSTAINED"
                    : "ANSWERED"}
              </h2>
              {fake && (
                <p className="lede" data-testid="fake-disclaimer">
                  TEST PROVIDER. Deterministic context and evidence below are the product.
                  The restatement is not model reasoning.
                </p>
              )}
              {fake ? (
                <details className="fake-answer">
                  <summary>Test provider restatement</summary>
                  <p>{answer.answer}</p>
                </details>
              ) : (
                <p>{answer.answer}</p>
              )}
              {!!answer.caveats?.length && (
                <p className="lede">{answer.caveats.join(" · ")}</p>
              )}
              {cited.length > 0 && (
                <ul className="evidence-list" data-testid="cited-evidence">
                  {cited.map((unit) => {
                    const value = formatEvidenceValue(unit.value);
                    return (
                      <li key={unit.ref} className="pass">
                        <strong>{unit.label}</strong>
                        {value ? <span> {value}</span> : null}
                        {unit.object_ref ? <span className="dim"> · {unit.object_ref}</span> : null}
                        <details className="raw-ref">
                          <summary>Details</summary>
                          <span className="mono">{unit.ref}</span>
                          {unit.kind ? <span className="dim"> · {unit.kind}</span> : null}
                          {unit.provenance ? <span className="dim"> · {unit.provenance}</span> : null}
                        </details>
                      </li>
                    );
                  })}
                </ul>
              )}
              {answer.grounding_status === "invalid" && (
                <p className="err">Grounding rejected: {answer.invalid_reason}</p>
              )}
              {!!answer.suggested_action && (
                <p data-testid="suggested-action">
                  Proposed action: {answer.suggested_action.action_type}
                  {answer.suggested_action.recommendation
                    ? ` · ${answer.suggested_action.recommendation}`
                    : ""}
                  {" "}(human approval required)
                </p>
              )}
            </section>
          )}
          {!!answer?.tool_trace?.length && (
            <details className="dev-trace" data-testid="tool-trace">
              <summary>Developer: tool execution</summary>
              <ul>
                {answer.tool_trace.map((step, i) => (
                  <li key={i}>{step.summary}</li>
                ))}
              </ul>
              <p className="lede">
                provider {answer.provider} · model {answer.model} · kind {answer.provider_kind}
              </p>
            </details>
          )}
          <section className="why-panel" data-testid="why">
            <h2>Why</h2>
            <p>{bundle.why}</p>
          </section>
          {requirements.length > 0 && (
            <Section title="Required evidence" testId="requirements">
              <ul className="req-list">
                {requirements.map((r) => (
                  <li key={r.concept} className={r.present ? "pass" : "fail"}>
                    {r.concept} {r.present ? "FOUND" : "MISSING"}
                  </li>
                ))}
              </ul>
            </Section>
          )}
          {!!bundle.missing_context?.length && (
            <section className="missing-panel" data-testid="missing-context">
              <h2>Missing context</h2>
              <ul>
                {bundle.missing_context.map((m) => (
                  <li key={m.concept}><strong>{m.concept}</strong><span>{m.reason}</span></li>
                ))}
              </ul>
            </section>
          )}
          <div className="grid context-grid">
            <Section title="Business objects" testId="objects">
              {objects.length ? objects.map((o) => (
                <div key={o.type + o.id} className="row">
                  <span><span className="obj-type">{o.type}</span> {itemLabel(o)}</span>
                  {o.type === "Item" && (
                    <button className="obj-link" onClick={() => onOpenObject(o)}>open</button>
                  )}
                </div>
              )) : <p className="lede">None assembled.</p>}
            </Section>
            <Section title="Relationships" testId="relationships">
              <RelationshipMap bundle={bundle} onOpen={onOpenObject} />
            </Section>
            <Section title="Decisive facts" testId="facts">
              {Object.keys(facts).length ? Object.entries(facts).map(([k, v]) => {
                if (v != null && typeof v === "object") {
                  if (k === "listing_as_of") {
                    const covered = (v as { covered?: boolean }).covered;
                    return <Field key={k} label="listing_as_of" value={covered ? "covered" : "not covered"} />;
                  }
                  return null;
                }
                return <Field key={k} label={k} value={v} />;
              }) : <p className="lede">None.</p>}
            </Section>
            <Section title="Metrics" testId="metrics">
              {bundle.metrics && Object.keys(bundle.metrics).length
                ? Object.entries(bundle.metrics).map(([k, v]) => <Field key={k} label={k} value={v} />)
                : <p className="lede">None.</p>}
            </Section>
            <Section title="Relevant history" testId="history">
              {(bundle.events || []).length
                ? bundle.events.map((e, i) => (
                    <p key={i} className="hist"><span className="mono dim">{e.at ?? "?"}</span> {e.type}</p>
                  ))
                : <p className="lede">None.</p>}
            </Section>
            <Section title="Rules" testId="rules">
              {(bundle.applicable_rules || []).length
                ? bundle.applicable_rules.map((r, i) => (
                    <p key={i}><strong>{String(r.name || "rule")}</strong> {r.definition ? `— ${String(r.definition)}` : ""}</p>
                  ))
                : <p className="lede">None.</p>}
            </Section>
            <Section title="Applicable policies" testId="policies">
              {((answer?.policies || bundle.applicable_policies) || []).length
                ? ((answer?.policies || bundle.applicable_policies) || []).map((p) => (
                    <p key={`${p.id}:${p.version}`}><strong>{p.id}:{p.version}</strong> — {p.title}</p>
                  ))
                : <p className="lede">None.</p>}
            </Section>
            <Section title="Unstructured evidence" testId="evidence">
              {bundle.retrieved_evidence?.length
                ? bundle.retrieved_evidence.map((ev) => (
                    <p key={String(ev.note_id || ev.title)}>
                      <strong>{String(ev.title || ev.kind)}</strong> — {String(ev.body || "")}
                    </p>
                  ))
                : <p className="lede">None for this question.</p>}
            </Section>
            <Section title="Provenance" testId="provenance">
              <Field label="source" value={provenance.tool} />
              <Field label="domain" value={provenance.domain || "resale"} />
              <Field label="as_of" value={provenance.as_of || bundle.as_of} />
              <Field label="services" value={(provenance.source_tools as string[] || []).join(", ") || "—"} />
              <button className="chip" onClick={() => setShowRaw((v) => !v)}>
                {showRaw ? "Hide raw" : "Raw JSON"}
              </button>
              {showRaw && <pre className="mono">{JSON.stringify(provenance, null, 2)}</pre>}
            </Section>
          </div>
        </>
      )}
    </>
  );
}
