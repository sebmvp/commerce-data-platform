import { useEffect, useMemo, useState, type ReactNode } from "react";
import { getContext, getEval, getItem, getItemHistory } from "./api";

type Tab = "inspect" | "eval" | "item";

const SAMPLES = [
  "Should I reprice j4-military-s?",
  "Should I reprice stone-cargo-l?",
  "What should I focus on today?",
  "What do seller notes say about stone-cargo-l?",
  "Can I trust the current business snapshot?",
];

function Pill({ ok, label }: { ok: boolean; label: string }) {
  return <span className={`pill ${ok ? "ok" : "bad"}`}>{label}</span>;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="card">
      <h2>{title}</h2>
      {children}
    </section>
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
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function runQuestion(q: string) {
    setBusy(true);
    setError(null);
    try {
      const data = await getContext(q);
      setBundle(data);
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

  return (
    <div className="app">
      <h1>Context Inspector</h1>
      <p className="lede">
        This system decides what business context an AI actually needs —
        objects, relationships, history, rules, and an explicit statement
        when required context is missing.
      </p>
      <div className="tabs">
        <button className={tab === "inspect" ? "active" : ""} onClick={() => setTab("inspect")}>
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
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask an operational question"
            />
            <button type="submit" disabled={busy}>
              Assemble
            </button>
          </form>
          <p className="lede">
            {SAMPLES.map((s) => (
              <button
                key={s}
                className="obj-link"
                style={{ marginRight: 6, marginBottom: 6 }}
                onClick={() => {
                  setQuestion(s);
                  void runQuestion(s);
                }}
              >
                {s}
              </button>
            ))}
          </p>
          {bundle && (
            <>
              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <Pill ok={bundle.sufficient} label={bundle.sufficient ? "sufficient" : "insufficient"} />
                <span className="lede" style={{ margin: 0 }}>
                  intent {bundle.intent}
                </span>
              </div>
              <div className="grid" style={{ marginTop: 12 }}>
                <Section title="Missing context">
                  {bundle.missing_context?.length ? (
                    <ul className="missing">
                      {bundle.missing_context.map((m: any) => (
                        <li key={m.concept}>
                          <strong>{m.concept}</strong> — {m.reason}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="lede">None. Required concepts are present.</p>
                  )}
                </Section>
                <Section title="Objects">
                  {objects.map((o: any) => (
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
                  ))}
                </Section>
                <Section title="Relationships">
                  <pre className="mono">
                    {(bundle.relationships || [])
                      .map((r: any) => `${r.from_ref} —${r.type}→ ${r.to_ref}`)
                      .join("\n") || "—"}
                  </pre>
                </Section>
                <Section title="Facts / metrics">
                  <pre className="mono">{JSON.stringify(bundle.metrics, null, 2)}</pre>
                </Section>
                <Section title="History">
                  <pre className="mono">
                    {(bundle.events || [])
                      .map((e: any) => `${e.at ?? "?"}  ${e.type}`)
                      .join("\n") || "—"}
                  </pre>
                </Section>
                <Section title="Rules">
                  <pre className="mono">{JSON.stringify(bundle.applicable_rules, null, 2)}</pre>
                </Section>
                <Section title="Unstructured evidence">
                  {bundle.retrieved_evidence?.length ? (
                    bundle.retrieved_evidence.map((ev: any) => (
                      <p key={ev.note_id}>
                        <strong>{ev.title || ev.kind}</strong> — {ev.body}
                      </p>
                    ))
                  ) : (
                    <p className="lede">None for this question.</p>
                  )}
                </Section>
                <Section title="Provenance">
                  <pre className="mono">{JSON.stringify(bundle.provenance, null, 2)}</pre>
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
              <p>
                <Pill ok={evalReport.ok} label={`${evalReport.passed}/${evalReport.implemented} passing`} />{" "}
                {evalReport.failed} failing · {evalReport.skipped} skipped · {evalReport.total} catalog
              </p>
              {evalReport.cases.map((c: any) => (
                <div
                  key={c.id}
                  className="row"
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
            <input value={sku} onChange={(e) => setSku(e.target.value)} placeholder="sku" />
            <button type="submit" disabled={busy}>
              Load
            </button>
          </form>
          {itemSkus.length > 0 && (
            <p>
              {itemSkus.map((id: string) => (
                <button key={id} className="obj-link" onClick={() => void loadItem(id)}>
                  {id}
                </button>
              ))}
            </p>
          )}
          {item && (
            <div className="grid">
              <Section title="Current state">
                <pre className="mono">{JSON.stringify(item.data?.item ?? item.data, null, 2)}</pre>
              </Section>
              <Section title="Listings">
                <pre className="mono">{JSON.stringify(item.data?.listings, null, 2)}</pre>
              </Section>
              <Section title="Orders">
                <pre className="mono">{JSON.stringify(item.data?.orders, null, 2)}</pre>
              </Section>
              <Section title="Timeline">
                <pre className="mono">{JSON.stringify(history?.data?.timeline, null, 2)}</pre>
              </Section>
            </div>
          )}
        </>
      )}
    </div>
  );
}
