import { useEffect, useMemo, useState, type ReactNode } from "react";
import { getAnswer, getContext, getEval, getItem, getItemHistory } from "./api";

type Tab = "inspect" | "eval" | "item";

const SAMPLES = [
  "Should I reprice j4-military-s?",
  "Should I reprice stone-cargo-l?",
  "What was the active listing state for j4-military-s two weeks ago?",
  "Which listings have strong attention but weak offer conversion?",
  "What should I focus on today?",
];

function kv(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function Section({
  title,
  children,
  testId,
}: {
  title: string;
  children: ReactNode;
  testId?: string;
}) {
  return (
    <section className="card" data-testid={testId}>
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function Field({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="field">
      <dt>{label}</dt>
      <dd className="mono">{kv(value)}</dd>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>("inspect");
  const [question, setQuestion] = useState(SAMPLES[0]);
  const [bundle, setBundle] = useState<any>(null);
  const [evalReport, setEvalReport] = useState<any>(null);
  const [sku, setSku] = useState("j4-military-s");
  const [item, setItem] = useState<any>(null);
  const [history, setHistory] = useState<any>(null);
  const [answer, setAnswer] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function runQuestion(q: string) {
    setBusy(true);
    setError(null);
    try {
      const data = await getContext(q);
      setBundle(data);
      setAnswer(null);
      setTab("inspect");
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function runEval() {
    setBusy(true);
    setError(null);
    try {
      setEvalReport(await getEval());
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function runAnswer(q: string) {
    setBusy(true);
    setError(null);
    try {
      setAnswer(await getAnswer(q));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadItem(id: string) {
    setBusy(true);
    setError(null);
    try {
      const [it, hist] = await Promise.all([getItem(id), getItemHistory(id)]);
      setItem(it);
      setHistory(hist);
      setSku(id);
      setTab("item");
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void runQuestion(SAMPLES[0]);
  }, []);

  const objects = bundle?.objects ?? [];
  const itemSkus = useMemo(
    () =>
      objects
        .filter((o: any) => o.type === "Item")
        .map((o: any) => o.id as string),
    [objects],
  );

  const facts = bundle?.facts ?? {};
  const itemData = item?.data?.item ?? item?.data ?? {};
  const listings = item?.data?.listings ?? [];
  const orders = item?.data?.orders ?? [];
  const timeline = history?.data?.timeline ?? [];

  return (
    <div className="app">
      <header>
        <h1>Context Inspector</h1>
        <p className="lede">
          This is the context the system assembled for this question —
          not a chatbot, and not a dump of the whole business.
        </p>
      </header>
      <div className="tabs">
        <button
          className={tab === "inspect" ? "active" : ""}
          onClick={() => setTab("inspect")}
        >
          Question
        </button>
        <button
          className={tab === "eval" ? "active" : ""}
          onClick={() => {
            setTab("eval");
            if (!evalReport) void runEval();
          }}
        >
          Evaluation
        </button>
        <button className={tab === "item" ? "active" : ""} onClick={() => setTab("item")}>
          Object
        </button>
      </div>
      {error && <p className="err">{error}</p>}

      {tab === "inspect" && (
        <>
          <form
            className="ask"
            onSubmit={(e) => {
              e.preventDefault();
              void runQuestion(question);
            }}
          >
            <input
              data-testid="question-input"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask an operational question"
            />
            <button type="submit" disabled={busy}>
              Assemble
            </button>
          </form>
          <div className="samples">
            {SAMPLES.map((s) => (
              <button
                key={s}
                className="chip"
                onClick={() => {
                  setQuestion(s);
                  void runQuestion(s);
                }}
              >
                {s}
              </button>
            ))}
          </div>
          {bundle && (
            <>
              <div
                className={`banner ${bundle.sufficient ? "ok" : "bad"}`}
                data-testid="sufficiency"
              >
                <div>
                  <div className="banner-kicker">{bundle.intent}</div>
                  <div className="banner-title">
                    {bundle.sufficient ? "SUFFICIENT" : "INSUFFICIENT"}
                  </div>
                </div>
                <p className="banner-q" data-testid="assembled-question">
                  {bundle.question}
                </p>
              </div>
              <div className="samples">
                <button
                  className="chip"
                  data-testid="grounded-answer"
                  disabled={busy}
                  onClick={() => void runAnswer(question)}
                >
                  Grounded answer
                </button>
              </div>
              {answer && (
                <section
                  className={`missing-panel ${answer.abstained ? "" : "ok-panel"}`}
                  data-testid="grounded-output"
                  style={
                    answer.abstained
                      ? undefined
                      : { borderColor: "#14532d", background: "#101610", color: "var(--fg)" }
                  }
                >
                  <h2>{answer.abstained ? "Abstained" : "Grounded answer"}</h2>
                  <p>{answer.answer}</p>
                  <p className="lede" style={{ marginTop: 8 }}>
                    provider {answer.provider}
                  </p>
                </section>
              )}

              {!!bundle.missing_context?.length && (
                <section className="missing-panel" data-testid="missing-context">
                  <h2>Missing context</h2>
                  <ul>
                    {bundle.missing_context.map((m: any) => (
                      <li key={m.concept}>
                        <strong>{m.concept}</strong>
                        <span>{m.reason}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <div className="grid">
                <Section title="Objects" testId="objects">
                  {objects.length ? (
                    objects.map((o: any) => (
                      <div key={o.type + o.id} className="row">
                        <span>
                          {o.type} <span className="mono">{o.id}</span>
                        </span>
                        {o.type === "Item" && (
                          <button className="obj-link" onClick={() => void loadItem(o.id)}>
                            open
                          </button>
                        )}
                      </div>
                    ))
                  ) : (
                    <p className="lede">None assembled.</p>
                  )}
                </Section>
                <Section title="Relationships" testId="relationships">
                  <pre className="mono">
                    {(bundle.relationships || [])
                      .map((r: any) => `${r.from_ref} —${r.type}→ ${r.to_ref}`)
                      .join("\n") || "—"}
                  </pre>
                </Section>
                <Section title="Facts" testId="facts">
                  {Object.keys(facts).length ? (
                    Object.entries(facts).map(([k, v]) => <Field key={k} label={k} value={v} />)
                  ) : (
                    <p className="lede">None.</p>
                  )}
                </Section>
                <Section title="Metrics" testId="metrics">
                  {bundle.metrics && Object.keys(bundle.metrics).length ? (
                    Object.entries(bundle.metrics).map(([k, v]) => (
                      <Field key={k} label={k} value={v} />
                    ))
                  ) : (
                    <p className="lede">None.</p>
                  )}
                </Section>
                <Section title="History" testId="history">
                  <pre className="mono">
                    {(bundle.events || [])
                      .map((e: any) => `${e.at ?? "?"}  ${e.type}`)
                      .join("\n") || "—"}
                  </pre>
                </Section>
                <Section title="Rules" testId="rules">
                  {(bundle.applicable_rules || []).length ? (
                    (bundle.applicable_rules as any[]).map((r, i) => (
                      <p key={i}>
                        <strong>{typeof r === "string" ? r : r.name || "rule"}</strong>
                        {typeof r === "object" && r.definition ? (
                          <span className="lede"> — {r.definition}</span>
                        ) : null}
                      </p>
                    ))
                  ) : (
                    <p className="lede">None.</p>
                  )}
                </Section>
                <Section title="Unstructured evidence" testId="evidence">
                  {bundle.retrieved_evidence?.length ? (
                    bundle.retrieved_evidence.map((ev: any) => (
                      <p key={ev.note_id || ev.title}>
                        <strong>{ev.title || ev.kind}</strong> — {ev.body}
                      </p>
                    ))
                  ) : (
                    <p className="lede">None for this question.</p>
                  )}
                </Section>
                <Section title="Provenance" testId="provenance">
                  <pre className="mono">{kv(bundle.provenance)}</pre>
                </Section>
              </div>
            </>
          )}
        </>
      )}

      {tab === "eval" && (
        <>
          <button className="obj-link" onClick={() => void runEval()} disabled={busy}>
            Re-run evaluation
          </button>
          {evalReport && (
            <>
              <div className="eval-bar" data-testid="eval-summary">
                <span>
                  TOTAL <strong data-testid="eval-total">{evalReport.total}</strong>
                </span>
                <span className="pass">
                  PASS <strong data-testid="eval-pass">{evalReport.passed}</strong>
                </span>
                <span className={evalReport.failed ? "fail" : ""}>
                  FAIL <strong data-testid="eval-fail">{evalReport.failed}</strong>
                </span>
                <span className={evalReport.skipped ? "fail" : "skip"}>
                  SKIP <strong data-testid="eval-skip">{evalReport.skipped}</strong>
                </span>
              </div>
              {evalReport.cases.map((c: any) => (
                <div
                  key={c.id}
                  className="row"
                  data-testid={`eval-case-${c.id}`}
                  onClick={() => {
                    setQuestion(c.question);
                    void runQuestion(c.question);
                  }}
                >
                  <span>
                    <span className={c.passed ? "pass" : c.skipped ? "skip" : "fail"}>
                      {c.passed ? "PASS" : c.skipped ? "SKIP" : "FAIL"}
                    </span>{" "}
                    {c.id} {c.question}
                  </span>
                  <span className="lede" style={{ margin: 0 }}>
                    {c.errors?.filter((e: string) => e !== "not implemented").join("; ")}
                  </span>
                </div>
              ))}
            </>
          )}
        </>
      )}

      {tab === "item" && (
        <>
          <form
            className="ask"
            onSubmit={(e) => {
              e.preventDefault();
              void loadItem(sku);
            }}
          >
            <input
              data-testid="sku-input"
              value={sku}
              onChange={(e) => setSku(e.target.value)}
              placeholder="sku"
            />
            <button type="submit" disabled={busy}>
              Load
            </button>
          </form>
          {itemSkus.length > 0 && (
            <p className="samples">
              {itemSkus.map((id: string) => (
                <button key={id} className="chip" onClick={() => void loadItem(id)}>
                  {id}
                </button>
              ))}
            </p>
          )}
          {item && (
            <div className="grid" data-testid="item-view">
              <Section title="Identity / current state" testId="item-state">
                <Field label="sku" value={itemData.sku} />
                <Field label="status" value={itemData.status} />
                <Field label="title" value={itemData.title} />
                <Field label="category" value={itemData.category} />
                <Field label="inventory age (days)" value={itemData.inventory_age_days} />
              </Section>
              <Section title="Acquisition">
                <Field label="acquisition cost CNY" value={itemData.acquisition_cost_cny} />
                <Field label="ordered at" value={itemData.ordered_at} />
                <Field label="received at" value={itemData.received_at} />
              </Section>
              <Section title="Listings / channel / engagement">
                {listings.length ? (
                  listings.map((l: any, i: number) => (
                    <div key={i} className="listing-block">
                      <Field label="platform" value={l.platform} />
                      <Field label="status" value={l.status} />
                      <Field label="price usd" value={l.price_usd} />
                      <Field label="listed at" value={l.listed_at} />
                      <Field label="views" value={l.views ?? l.engagement?.views} />
                      <Field label="watchers" value={l.watchers ?? l.engagement?.watchers} />
                      <Field label="offers" value={l.offers ?? l.engagement?.offers} />
                    </div>
                  ))
                ) : (
                  <p className="lede">No listings.</p>
                )}
              </Section>
              <Section title="Orders">
                {orders.length ? (
                  orders.map((o: any, i: number) => (
                    <div key={i}>
                      <Field label="order" value={o.order_id || o.id} />
                      <Field label="sold at" value={o.sold_at} />
                      <Field label="sale usd" value={o.sale_price_usd || o.price_usd} />
                    </div>
                  ))
                ) : (
                  <p className="lede">No orders.</p>
                )}
              </Section>
              <Section title="Timeline / history" testId="item-timeline">
                <pre className="mono">
                  {timeline
                    .map((e: any) => `${e.at ?? "?"}  ${e.type}`)
                    .join("\n") || "—"}
                </pre>
              </Section>
            </div>
          )}
        </>
      )}
    </div>
  );
}
