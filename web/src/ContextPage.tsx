import { useState } from "react";
import { RelationshipMap } from "./RelationshipMap";
import type { ContextBundle, ContextObject } from "./types";
import { Field, itemLabel, objectLabel, relVerb, Section } from "./ui";

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
        <button type="submit" disabled={busy}>Assemble</button>
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
              <div className="banner-kicker">{bundle.intent}{bundle.as_of ? ` · as of ${bundle.as_of}` : ""}</div>
              <div className="banner-title">{bundle.sufficient ? "SUFFICIENT" : "INSUFFICIENT"}</div>
            </div>
            <p className="banner-q" data-testid="assembled-question">{bundle.question}</p>
          </div>
          {answer && (
            <section className={`missing-panel ${answer.abstained ? "" : "ok-panel"}`} data-testid="grounded-output">
              <h2 data-testid="grounded-answer">{answer.abstained ? "Abstained" : "Grounded answer"}</h2>
              <p>{answer.answer}</p>
              {!!answer.caveats?.length && (
                <p className="lede">{(answer.caveats as string[]).join(" · ")}</p>
              )}
            </section>
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
              {(bundle.relationships || []).map((r, i) => (
                <p key={i} className="rel">
                  <strong>{objectLabel(objects, r.from_ref)}</strong>
                  <span className="rel-verb"> {relVerb(r.type)} </span>
                  <strong>{objectLabel(objects, r.to_ref)}</strong>
                </p>
              ))}
            </Section>
            <Section title="Facts / metrics" testId="facts">
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
