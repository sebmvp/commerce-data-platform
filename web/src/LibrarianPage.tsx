import { useState } from "react";
import { ObjectGraph } from "./ObjectGraph";
import {
  decisiveCards,
  formatWhy,
  humanLabel,
  itemLabel,
  kv,
  observedDate,
  typeLabel,
} from "./format";
import { Field, Section } from "./ui";
import type { ContextBundle, ContextObject, LibrarianResponse } from "./types";

const SAMPLES = [
  "Should I review the price of this listing?",
  "Should I reprice stone-cargo-l?",
  "What should I focus on today?",
  "What was the active listing state for j4-military-s two weeks ago?",
];

export function LibrarianPage({
  question,
  setQuestion,
  bundle,
  answer,
  busy,
  boundLabel,
  onAsk,
  onOpenObject,
}: {
  question: string;
  setQuestion: (q: string) => void;
  bundle: ContextBundle | null;
  answer: LibrarianResponse | null;
  busy: boolean;
  boundLabel?: string | null;
  onAsk: (q: string) => void;
  onOpenObject: (obj: ContextObject) => void;
}) {
  const [showRaw, setShowRaw] = useState(false);
  const objects = bundle?.objects ?? [];
  const facts = bundle?.facts ?? {};
  const provenance = bundle?.provenance || {};
  const requirements = bundle?.requirements || [];
  const fake = answer?.provider === "fake" || answer?.provider_kind === "fake";
  const cards = decisiveCards(answer, bundle);
  const observed = observedDate(bundle?.as_of);

  return (
    <div data-testid="librarian-page" className="librarian">
      {!boundLabel && (
        <p className="lede">
          Retrieves the business context required for a question and identifies
          missing evidence before answering.
        </p>
      )}
      {boundLabel ? <div className="bound-chip">Bound to {boundLabel}</div> : null}
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
          placeholder="Ask the Business Librarian"
        />
        <button className="btn-primary" type="submit" disabled={busy}>
          Ask the Business Librarian
        </button>
      </form>
      {!boundLabel && (
        <div className="samples">
          {SAMPLES.map((s) => (
            <button
              key={s}
              className="chip"
              onClick={() => {
                setQuestion(s);
                onAsk(s);
              }}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {busy && !bundle ? <p className="empty">Assembling context…</p> : null}

      {bundle && (
        <>
          {answer && (
            <section
              className={`answer-block ${
                answer.grounding_status === "grounded"
                  ? "ok-panel"
                  : answer.grounding_status === "invalid"
                    ? "invalid-panel"
                    : ""
              }`}
              data-testid="grounded-output"
            >
              <div className="kicker" data-testid="grounded-answer">
                {answer.grounding_status === "invalid"
                  ? "Invalid model output"
                  : answer.abstained
                    ? "Abstained"
                    : "Answer"}
              </div>
              {fake && (
                <p className="lede tight" data-testid="fake-disclaimer">
                  Test provider — extractive restatement, not model reasoning.
                </p>
              )}
              {fake && !answer.abstained ? (
                <>
                  <p className="answer-text">
                    Context is sufficient. Decisive evidence is below.
                  </p>
                  <details className="fake-answer">
                    <summary>Test provider restatement</summary>
                    <p>{answer.answer}</p>
                  </details>
                </>
              ) : (
                <p className="answer-text">{answer.answer}</p>
              )}
              {!!answer.caveats?.length && <p className="lede tight">{answer.caveats.join(" · ")}</p>}
              {!!answer.suggested_action && (
                <p data-testid="suggested-action" className="proposal">
                  Proposed sandbox action: {humanLabel(answer.suggested_action.action_type)}
                  {answer.suggested_action.recommendation
                    ? ` · ${humanLabel(String(answer.suggested_action.recommendation))}`
                    : ""}{" "}
                  (human approval required)
                </p>
              )}
            </section>
          )}

          <div className={`banner ${bundle.sufficient ? "ok" : "bad"}`} data-testid="sufficiency">
            <div>
              <div className="banner-kicker" data-testid="interpreted-plan">
                {humanLabel(String(answer?.plan?.capability || bundle.intent))}
                {bundle.as_of ? ` · as of ${observed || bundle.as_of}` : ""}
              </div>
              <div className="banner-title">{bundle.sufficient ? "SUFFICIENT" : "INSUFFICIENT"}</div>
            </div>
            <p className="banner-q" data-testid="assembled-question">
              {bundle.question}
            </p>
          </div>

          <section className="why-panel" data-testid="why">
            <h2>Why</h2>
            <p>{formatWhy(bundle.why)}</p>
          </section>

          {cards.length > 0 && (
            <section>
              <h2>Decisive evidence</h2>
              <div className="evidence-grid" data-testid="cited-evidence">
                {cards.map((card) => (
                  <div key={card.label} className="evidence-card">
                    <div className="ev-label">{card.label}</div>
                    <div className="ev-value">{card.value}</div>
                    {card.source ? <div className="ev-src">{card.source}</div> : null}
                    {card.observed ? <div className="ev-src">observed {card.observed}</div> : null}
                    {card.ref ? (
                      <details className="raw-ref">
                        <summary>Details</summary>
                        <span className="mono">{card.ref}</span>
                      </details>
                    ) : null}
                  </div>
                ))}
              </div>
            </section>
          )}

          <Section title="Related objects" testId="objects">
            {objects.length ? (
              <div className="related-split">
                <div>
                  {objects.map((o) => (
                    <div key={o.type + o.id} className="row">
                      <span>
                        <span className="og-type">{typeLabel(o.type)}</span> {itemLabel(o)}
                      </span>
                      {o.type === "Item" && (
                        <button className="obj-link" onClick={() => onOpenObject(o)}>
                          open
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                <div data-testid="relationships">
                  <ObjectGraph bundle={bundle} onOpen={onOpenObject} />
                </div>
              </div>
            ) : (
              <p className="empty">None assembled.</p>
            )}
          </Section>

          {!!bundle.missing_context?.length && (
            <section className="missing-panel" data-testid="missing-context">
              <h2>Missing context</h2>
              <ul>
                {bundle.missing_context.map((m) => (
                  <li key={m.concept}>
                    <strong>{humanLabel(m.concept)}</strong>
                    <span>{formatWhy(m.reason)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {answer?.grounding_status === "invalid" && (
            <p className="err">Grounding rejected: {answer.invalid_reason}</p>
          )}

          <div className="grid secondary-grid">
            <Section title="Facts" testId="facts">
              {Object.keys(facts).length ? (
                Object.entries(facts).map(([k, v]) => {
                  if (k === "sku") return null;
                  if (v != null && typeof v === "object") {
                    if (k === "listing_as_of") {
                      const covered = (v as { covered?: boolean }).covered;
                      return <Field key={k} label="listing as-of" value={covered ? "covered" : "not covered"} />;
                    }
                    if (k === "deltas" || k === "previous_snapshot" || k === "current_snapshot") return null;
                    return null;
                  }
                  return <Field key={k} label={humanLabel(k)} value={v} />;
                })
              ) : (
                <p className="empty">None.</p>
              )}
            </Section>
            <Section title="Metrics" testId="metrics">
              {bundle.metrics && Object.keys(bundle.metrics).length ? (
                Object.entries(bundle.metrics).map(([k, v]) => (
                  <Field key={k} label={humanLabel(k)} value={formatEvidenceSafe(k, v)} />
                ))
              ) : (
                <p className="empty">None.</p>
              )}
            </Section>
            <Section title="History" testId="history">
              {(bundle.events || []).length ? (
                bundle.events.slice(0, 8).map((e, i) => (
                  <p key={i} className="hist">
                    <span className="dim">{observedDate(e.at) || "—"}</span> {humanLabel(e.type)}
                  </p>
                ))
              ) : (
                <p className="empty">None.</p>
              )}
            </Section>
            <Section title="Rules & policies" testId="rules">
              {(bundle.applicable_rules || []).length ? (
                bundle.applicable_rules.map((r, i) => (
                  <p key={i}>
                    <strong>{humanLabel(String(r.name || "rule"))}</strong>
                    {r.definition ? ` — ${String(r.definition)}` : ""}
                  </p>
                ))
              ) : (
                <p className="empty">None.</p>
              )}
              <div data-testid="policies">
                {((answer?.policies || bundle.applicable_policies) || []).map((p) => (
                  <p key={`${p.id}:${p.version}`}>{p.title || humanLabel(p.id)}</p>
                ))}
              </div>
            </Section>
            <Section title="Notes" testId="evidence">
              {bundle.retrieved_evidence?.length ? (
                bundle.retrieved_evidence.map((ev) => (
                  <p key={String(ev.note_id || ev.title)}>
                    <strong>{String(ev.title || ev.kind)}</strong> — {String(ev.body || "")}
                  </p>
                ))
              ) : (
                <p className="empty">None for this question.</p>
              )}
            </Section>
          </div>

          <details className="dev-trace" data-testid="provenance" style={{ marginTop: 12 }}>
            <summary>Details — provenance, required evidence, ContextBundle, tool trace</summary>
            {requirements.length > 0 && (
              <div data-testid="requirements">
                <h2>Required evidence</h2>
                <ul className="req-list">
                  {requirements.map((r) => (
                    <li key={r.concept} className={r.present ? "pass" : "fail"}>
                      {humanLabel(r.concept)} {r.present ? "found" : "missing"}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <Field label="source" value={provenance.tool} />
            <Field label="domain" value={provenance.domain || "resale"} />
            <Field label="as of" value={observed || provenance.as_of || bundle.as_of} />
            <Field label="services" value={(provenance.source_tools as string[] || []).join(", ") || "—"} />
            {!!answer?.tool_trace?.length && (
              <div data-testid="tool-trace">
                <h2>Tool trace</h2>
                <ul>
                  {answer.tool_trace.map((step, i) => (
                    <li key={i}>{step.summary}</li>
                  ))}
                </ul>
                <p className="lede">
                  provider {answer.provider} · model {answer.model} · kind {answer.provider_kind}
                </p>
              </div>
            )}
            <button className="chip" onClick={() => setShowRaw((v) => !v)}>
              {showRaw ? "Hide raw ContextBundle" : "Raw ContextBundle"}
            </button>
            {showRaw && <pre className="mono">{JSON.stringify(bundle, null, 2)}</pre>}
          </details>
        </>
      )}
    </div>
  );
}

function formatEvidenceSafe(key: string, value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "number") {
    if (/rate/i.test(key) && value > 0 && value < 1) return `${(value * 100).toFixed(1)}%`;
    if (/age|days/i.test(key)) return `${value} days`;
    if (/cny/i.test(key)) return `${Number(value).toLocaleString()} CNY`;
    if (/usd|price|cost/i.test(key)) return `$${Number(value).toLocaleString()}`;
    return String(value);
  }
  return kv(value);
}
