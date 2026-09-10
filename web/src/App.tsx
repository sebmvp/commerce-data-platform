import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  getAnswer,
  getAttention,
  getContext,
  getEval,
  getEvalCompare,
  getIngestRuns,
  getIngestTrust,
  getInventoryItems,
  getItem,
  getItemHistory,
  getSnapshot,
} from "./api";

type Tab = "overview" | "inventory" | "context" | "eval" | "health";

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
  className = "",
}: {
  title: string;
  children: ReactNode;
  testId?: string;
  className?: string;
}) {
  return (
    <section className={`card ${className}`} data-testid={testId}>
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

function objectLabel(objects: any[], ref: string): string {
  const idx = ref.indexOf(":");
  const type = idx === -1 ? ref : ref.slice(0, idx);
  const id = idx === -1 ? "" : ref.slice(idx + 1);
  const obj = objects.find((o) => o.type === type && String(o.id) === id);
  const props = obj?.properties || {};
  if (type === "Item") return props.product || id || ref;
  if (type === "Listing") {
    const platform = props.platform ? String(props.platform) : "listing";
    const title = platform.charAt(0).toUpperCase() + platform.slice(1);
    return `${title} listing`;
  }
  if (type === "Channel") {
    const platform = props.platform || id;
    return String(platform).charAt(0).toUpperCase() + String(platform).slice(1);
  }
  if (type === "Order") return `order ${id}`;
  if (type === "Recommendation") return `recommendation for ${props.sku || id}`;
  if (type === "EngagementObservation") return "engagement";
  if (type === "IngestRun") return "ingest trust";
  return obj ? `${type} ${id}` : ref;
}

function relVerb(type: string): string {
  const map: Record<string, string> = {
    HAS_LISTING: "listed as",
    ON_CHANNEL: "on",
    HAS_ENGAGEMENT: "has",
    RESULTED_IN: "sold as",
    TARGETS: "targets",
  };
  return map[type] || type.toLowerCase().replace(/_/g, " ");
}

function itemLabel(obj: any): string {
  if (obj.type === "Item") return obj.properties?.product || obj.id;
  if (obj.type === "Listing") {
    const platform = obj.properties?.platform || "listing";
    return `${platform} listing`;
  }
  if (obj.type === "Channel") return obj.properties?.platform || obj.id;
  if (obj.type === "Order") return `order ${obj.id}`;
  if (obj.type === "Recommendation") return `rec · ${obj.properties?.sku || obj.id}`;
  if (obj.type === "EngagementObservation") return "engagement";
  if (obj.type === "IngestRun") return "ingest trust";
  return `${obj.type} ${obj.id}`;
}

export default function App() {
  const [tab, setTab] = useState<Tab>("context");
  const [question, setQuestion] = useState(SAMPLES[0]);
  const [bundle, setBundle] = useState<any>(null);
  const [evalReport, setEvalReport] = useState<any>(null);
  const [compare, setCompare] = useState<any>(null);
  const [sku, setSku] = useState("j4-military-s");
  const [item, setItem] = useState<any>(null);
  const [history, setHistory] = useState<any>(null);
  const [answer, setAnswer] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showRawIds, setShowRawIds] = useState(false);
  const [showRawProvenance, setShowRawProvenance] = useState(false);
  const [snapshot, setSnapshot] = useState<any>(null);
  const [attention, setAttention] = useState<any>(null);
  const [inventory, setInventory] = useState<any[]>([]);
  const [invFilter, setInvFilter] = useState("");
  const [trust, setTrust] = useState<any>(null);
  const [ingestRuns, setIngestRuns] = useState<any[]>([]);

  async function runQuestion(q: string) {
    setBusy(true);
    setError(null);
    try {
      const data = await getContext(q);
      setBundle(data);
      try {
        setAnswer(await getAnswer(q));
      } catch (err) {
        setAnswer(null);
        setError(String(err));
      }
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
      const [engine, cmp] = await Promise.all([getEval(), getEvalCompare()]);
      setEvalReport(engine);
      setCompare(cmp);
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
      setTab("inventory");
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadOverview() {
    setBusy(true);
    setError(null);
    try {
      const [snap, att] = await Promise.all([getSnapshot(), getAttention()]);
      setSnapshot(snap);
      setAttention(att);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadHealth() {
    setBusy(true);
    setError(null);
    try {
      const [t, runs] = await Promise.all([getIngestTrust(), getIngestRuns()]);
      setTrust(t);
      setIngestRuns(Array.isArray(runs) ? runs : runs?.data || []);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadInventory(status?: string) {
    setBusy(true);
    setError(null);
    try {
      setInventory(await getInventoryItems(status || undefined));
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
  const provenance = bundle?.provenance || {};
  const lexical = compare?.lexical || compare?.rag;

  return (
    <div className="app">
      <header>
        <h1>Commerce Data Platform</h1>
        <p className="lede">
          Operational context for the resale business — objects, history,
          rules, and missing evidence. Not a chatbot dump of the warehouse.
        </p>
      </header>
      <div className="tabs">
        <button
          className={tab === "overview" ? "active" : ""}
          onClick={() => {
            setTab("overview");
            if (!snapshot) void loadOverview();
          }}
        >
          Overview
        </button>
        <button
          className={tab === "inventory" ? "active" : ""}
          onClick={() => {
            setTab("inventory");
            if (!inventory.length) void loadInventory();
          }}
        >
          Inventory
        </button>
        <button
          className={tab === "context" ? "active" : ""}
          onClick={() => setTab("context")}
        >
          Context
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
        <button
          className={tab === "health" ? "active" : ""}
          onClick={() => {
            setTab("health");
            if (!trust) void loadHealth();
          }}
        >
          Data Health
        </button>
      </div>
      {error && <p className="err">{error}</p>}

      {tab === "overview" && (
        <>
          {snapshot && (
            <div className="grid">
              <Section title="Inventory state">
                <Field label="items" value={snapshot.data?.items_total} />
                <Field label="owned unlisted" value={snapshot.data?.owned_unlisted} />
                <Field label="listed" value={snapshot.data?.listed_items} />
                <Field label="sold" value={snapshot.data?.sold_items} />
                <Field label="active listings" value={snapshot.data?.active_listings} />
              </Section>
              <Section title="Capital and sales">
                <Field label="capital tied up CNY" value={snapshot.data?.capital_tied_up_cny} />
                <Field label="USD estimate (display FX)" value={snapshot.data?.capital_tied_up_usd_est} />
                <Field label="realized revenue USD" value={snapshot.data?.realized_revenue_usd} />
                <Field label="gross after fees USD" value={snapshot.data?.realized_gross_after_fees_usd} />
                <p className="lede">Fee-adjusted revenue is not margin. Acquisition cost is separate.</p>
              </Section>
            </div>
          )}
          {attention && (
            <Section title="Attention items">
              {(attention.data?.recommendations || []).slice(0, 8).map((r: any) => (
                <div key={r.sku} className="row" onClick={() => void loadItem(r.sku)}>
                  <span>
                    <strong>{r.sku}</strong> {r.action || r.attention_reason}
                  </span>
                  <span className="lede" style={{ margin: 0 }}>{r.why}</span>
                </div>
              ))}
            </Section>
          )}
        </>
      )}

      {tab === "context" && (
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

              <section className="why-panel" data-testid="why">
                <h2>Why</h2>
                <p>{bundle.why || "Required concepts were checked against assembled evidence."}</p>
              </section>

              {answer && (
                <section
                  className={`missing-panel ${answer.abstained ? "" : "ok-panel"}`}
                  data-testid="grounded-output"
                >
                  <h2 data-testid="grounded-answer">{answer.abstained ? "Abstained" : "Grounded answer"}</h2>
                  <p>{answer.answer}</p>
                  <p className="lede" style={{ marginTop: 8 }}>
                    provider {answer.provider}
                    {answer.abstained ? " — insufficient context, no invented facts" : ""}
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
                <Section title="Business objects" testId="objects">
                  {objects.length ? (
                    objects.map((o: any) => (
                      <div key={o.type + o.id} className="row">
                        <span>
                          <span className="obj-type">{o.type}</span>{" "}
                          {itemLabel(o)}
                          {showRawIds && <span className="mono dim"> {o.id}</span>}
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
                  {(bundle.relationships || []).length ? (
                    <>
                      {(bundle.relationships as any[]).map((r, i) => (
                        <p key={i} className="rel">
                          <strong>{objectLabel(objects, r.from_ref)}</strong>
                          <span className="rel-verb"> {relVerb(r.type)} </span>
                          <strong>{objectLabel(objects, r.to_ref)}</strong>
                        </p>
                      ))}
                      <button className="chip" onClick={() => setShowRawIds((v) => !v)}>
                        {showRawIds ? "Hide raw ids" : "Show raw ids"}
                      </button>
                      {showRawIds && (
                        <pre className="mono dim">
                          {(bundle.relationships || [])
                            .map((r: any) => `${r.from_ref} —${r.type}→ ${r.to_ref}`)
                            .join("\n")}
                        </pre>
                      )}
                    </>
                  ) : (
                    <p className="lede">None.</p>
                  )}
                </Section>
                <Section title="Facts / metrics" testId="facts">
                  {Object.keys(facts).length ? (
                    Object.entries(facts).map(([k, v]) => {
                      if (v != null && typeof v === "object") {
                        if (k === "listing_as_of") {
                          const covered = (v as any).covered;
                          return (
                            <Field
                              key={k}
                              label="listing_as_of"
                              value={covered ? "covered" : "not covered"}
                            />
                          );
                        }
                        return null;
                      }
                      return <Field key={k} label={k} value={v} />;
                    })
                  ) : (
                    <p className="lede">None.</p>
                  )}
                  {bundle.metrics && Object.keys(bundle.metrics).length
                    ? Object.entries(bundle.metrics).map(([k, v]) => (
                        <Field key={`m-${k}`} label={k} value={v} />
                      ))
                    : null}
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
                <Section title="Relevant history" testId="history">
                  {(bundle.events || []).length ? (
                    (bundle.events as any[]).map((e, i) => (
                      <p key={i} className="hist">
                        <span className="mono dim">{e.at ?? "?"}</span> {e.type}
                      </p>
                    ))
                  ) : (
                    <p className="lede">None.</p>
                  )}
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
                  <Field label="source" value={provenance.tool} />
                  <Field label="domain" value={provenance.domain || "resale"} />
                  <Field label="as_of" value={provenance.as_of || bundle.as_of} />
                  <Field
                    label="services"
                    value={(provenance.source_tools || []).join(", ") || "—"}
                  />
                  <Field
                    label="relations"
                    value={(provenance.source_relations || []).join(", ") || "—"}
                  />
                  <button className="chip" onClick={() => setShowRawProvenance((v) => !v)}>
                    {showRawProvenance ? "Hide raw" : "Raw JSON"}
                  </button>
                  {showRawProvenance && <pre className="mono">{kv(provenance)}</pre>}
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
              <p className="lede" style={{ marginTop: 12 }}>
                {evalReport.suite || "GOLD / DEVELOPMENT"} — scores the Context Engine,
                not an LLM. Held-out scenario validation is `make eval-heldout`.
              </p>
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
              {lexical && (
                <div className="compare-bar" data-testid="eval-compare">
                  <div>
                    <div className="banner-kicker">Context Engine</div>
                    <div className="compare-n">
                      {compare.engine.passed}/{compare.engine.total}
                    </div>
                  </div>
                  <div>
                    <div className="banner-kicker">Lexical retrieval</div>
                    <div className="compare-n" data-testid="lexical-pass">
                      {lexical.passed}/{lexical.total}
                    </div>
                    <p className="lede" style={{ margin: "4px 0 0" }}>
                      TF-IDF over serialized rows. No generation.
                    </p>
                  </div>
                </div>
              )}
              {evalReport.cases.map((c: any) => (
                <div
                  key={c.id}
                  className="row"
                  data-testid={`eval-case-${c.id}`}
                  onClick={() => {
                    setQuestion(c.question);
                    setTab("context");
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

      {tab === "inventory" && (
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
          <div className="samples">
            {["", "owned", "listed", "sold"].map((st) => (
              <button
                key={st || "all"}
                className={`chip ${invFilter === st ? "active" : ""}`}
                onClick={() => {
                  setInvFilter(st);
                  void loadInventory(st);
                }}
              >
                {st || "all"}
              </button>
            ))}
          </div>
          {inventory.length > 0 && (
            <Section title="Items">
              {inventory.map((row: any) => (
                <div key={row.sku} className="row" onClick={() => void loadItem(row.sku)}>
                  <span>
                    <strong>{row.product || row.sku}</strong>
                    <span className="dim"> {row.sku}</span>
                  </span>
                  <span className="lede" style={{ margin: 0 }}>{row.status}</span>
                </div>
              ))}
            </Section>
          )}
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
                <Field label="title" value={itemData.product || itemData.title} />
                <Field label="category" value={itemData.category || itemData.category_key} />
                <Field label="inventory age (days)" value={itemData.inventory_age_days} />
              </Section>
              <Section title="Acquisition">
                <Field label="acquisition cost CNY" value={itemData.acquisition_cost_cny} />
                <Field label="acquired at" value={itemData.acquired_at || itemData.ordered_at} />
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
                      <Field label="sold at" value={o.sold_at || o.order_at} />
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

      {tab === "health" && (
        <>
          {trust && (
            <div className={`banner ${trust.ok ? "ok" : "bad"}`}>
              <div>
                <div className="banner-kicker">ingest trust</div>
                <div className="banner-title">{trust.ok ? "OK" : "NOT OK"}</div>
              </div>
              <p className="banner-q">{(trust.reasons || []).join(" ") || "Latest ingest reconciled."}</p>
            </div>
          )}
          <Section title="Recent ingest runs">
            {ingestRuns.length ? (
              ingestRuns.slice(0, 12).map((run: any) => (
                <div key={run.run_id || run.source} className="row">
                  <span>
                    <strong>{run.source}</strong> {run.status}
                  </span>
                  <span className="lede" style={{ margin: 0 }}>
                    loaded {run.rows_loaded ?? "—"} · rejected {run.rows_rejected ?? "—"}
                  </span>
                </div>
              ))
            ) : (
              <p className="lede">No ingest runs in this database.</p>
            )}
          </Section>
        </>
      )}
    </div>
  );
}
