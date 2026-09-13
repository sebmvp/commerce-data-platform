import { useState } from "react";
import { RelationshipMap } from "./RelationshipMap";
import type { ContextBundle, ContextObject } from "./types";
import { Field, itemLabel, Section } from "./ui";

const SAMPLES = [
  "Should I reprice j4-military-s?",
  "Should I reprice stone-cargo-l?",
  "What was the active listing state for j4-military-s two weeks ago?",
  "Which listings have strong attention but weak offer conversion?",
  "What should I focus on today?",
];

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
  answer: any;
  busy: boolean;
  onAsk: (q: string) => void;
  onOpenObject: (obj: ContextObject) => void;
}) {
  const [showRaw, setShowRaw] = useState(false);
  const objects = bundle?.objects ?? [];
  const facts = bundle?.facts ?? {};
  const provenance = bundle?.provenance || {};
  const requirements = bundle?.requirements || [];

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
              {answer.provider === "fake" && (
                <p className="lede" data-testid="fake-disclaimer">
                  Fake / Test provider. This restates bundle values; it is not model reasoning.
                </p>
              )}
              <p>{answer.answer}</p>
              {!!answer.caveats?.length && (
                <p className="lede">{(answer.caveats as string[]).join(" · ")}</p>
              )}
              {!!answer.evidence_refs?.length && (
                <ul className="req-list" data-testid="cited-evidence">
                  {answer.evidence_refs.map((ref: string) => (
                    <li key={ref} className="pass">{ref}</li>
                  ))}
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
                {(answer.tool_trace as Array<{ summary: string }>).map((step, i) => (
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
          <div className="grid">
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
                    return <Field key={k} label="listing_as_of" value={(v as any).covered ? "covered" : "not covered"} />;
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
                ? bundle.applicable_rules.map((r: any, i) => (
                    <p key={i}><strong>{r.name || "rule"}</strong> {r.definition ? `— ${r.definition}` : ""}</p>
                  ))
                : <p className="lede">None.</p>}
            </Section>
            <Section title="Applicable policies" testId="policies">
              {((answer?.policies || bundle.applicable_policies) || []).length
                ? ((answer?.policies || bundle.applicable_policies) as Array<Record<string, string>>).map((p) => (
                    <p key={p.id}><strong>{p.id}:{p.version}</strong> — {p.title}</p>
                  ))
                : <p className="lede">None.</p>}
            </Section>
            <Section title="Unstructured evidence" testId="evidence">
              {bundle.retrieved_evidence?.length
                ? bundle.retrieved_evidence.map((ev: any) => (
                    <p key={ev.note_id || ev.title}><strong>{ev.title || ev.kind}</strong> — {ev.body}</p>
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
