import { useEffect, useMemo, useState } from "react";
import {
  getAttention,
  getCompleteness,
  getContext,
  getEval,
  getEvalAnswers,
  getEvalLibrarian,
  getEvalPlan,
  getEvalCompare,
  getIngestRuns,
  getIngestTrust,
  getInventoryItems,
  getItem,
  getItemHistory,
  getRuntime,
  getSnapshot,
  postAnswer,
} from "./api";
import { EvaluationPage } from "./EvaluationPage";
import { HealthPage } from "./HealthPage";
import { InventoryPage } from "./InventoryPage";
import { LibrarianPage } from "./LibrarianPage";
import { ObjectView } from "./ObjectView";
import { OverviewPage } from "./OverviewPage";
import { observedDate, parseSnapshotDeltas, productName } from "./format";
import type {
  AttentionQueue,
  AttentionQueueRow,
  BusinessSnapshot,
  CompletenessReport,
  ContextBundle,
  ContextObject,
  EvalLayerReport,
  IngestRun,
  InventoryRow,
  ItemHistory,
  ItemPayload,
  LibrarianResponse,
  RuntimeInfo,
  TrustReport,
  View,
} from "./types";

const NAV: Array<{ id: View; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "inventory", label: "Inventory" },
  { id: "librarian", label: "Librarian" },
  { id: "eval", label: "Evaluation" },
  { id: "health", label: "Data Health" },
];

export default function App() {
  const [view, setView] = useState<View>("overview");
  const [question, setQuestion] = useState("Should I review the price of this listing?");
  const [bundle, setBundle] = useState<ContextBundle | null>(null);
  const [evalReport, setEvalReport] = useState<EvalLayerReport | null>(null);
  const [compare, setCompare] = useState<EvalLayerReport | null>(null);
  const [answers, setAnswers] = useState<EvalLayerReport | null>(null);
  const [planEval, setPlanEval] = useState<EvalLayerReport | null>(null);
  const [librarianEval, setLibrarianEval] = useState<EvalLayerReport | null>(null);
  const [sku, setSku] = useState<string | null>(null);
  const [item, setItem] = useState<ItemPayload | null>(null);
  const [history, setHistory] = useState<ItemHistory | null>(null);
  const [answer, setAnswer] = useState<LibrarianResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [askBusy, setAskBusy] = useState(false);
  const [snapshot, setSnapshot] = useState<BusinessSnapshot | null>(null);
  const [attention, setAttention] = useState<AttentionQueue | null>(null);
  const [inventory, setInventory] = useState<InventoryRow[]>([]);
  const [invFilter, setInvFilter] = useState("");
  const [trust, setTrust] = useState<TrustReport | null>(null);
  const [ingestRuns, setIngestRuns] = useState<IngestRun[]>([]);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [completeness, setCompleteness] = useState<CompletenessReport | null>(null);
  const [changes, setChanges] = useState<Array<{ label: string; detail: string }>>([]);
  const [split, setSplit] = useState(false);
  const [showObject, setShowObject] = useState(false);

  async function runQuestion(q: string, itemSku?: string) {
    setAskBusy(true);
    setError(null);
    try {
      const data = await postAnswer(q, itemSku);
      setBundle(data.bundle || null);
      setAnswer(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setAskBusy(false);
    }
  }

  async function runEval() {
    setBusy(true);
    setError(null);
    try {
      const [engine, cmp, ans, plan, librarian] = await Promise.all([
        getEval(),
        getEvalCompare(),
        getEvalAnswers(),
        getEvalPlan(),
        getEvalLibrarian(),
      ]);
      setEvalReport(engine);
      setCompare(cmp);
      setAnswers(ans);
      setPlanEval(plan);
      setLibrarianEval(librarian);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadItem(id: string, opts?: { view?: View; split?: boolean }) {
    setBusy(true);
    setError(null);
    try {
      const [it, hist] = await Promise.all([getItem(id), getItemHistory(id)]);
      setItem(it);
      setHistory(hist);
      setSku(id);
      setShowObject(true);
      if (opts?.split) setSplit(true);
      if (opts?.view) setView(opts.view);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadOverview() {
    setBusy(true);
    try {
      const [snap, att, rt, recent] = await Promise.all([
        getSnapshot(),
        getAttention(),
        getRuntime(),
        getContext("What changed since the previous snapshot?").catch(() => null),
      ]);
      setSnapshot(snap);
      setAttention(att);
      setRuntime(rt);
      setChanges(parseSnapshotDeltas(recent?.facts, recent?.metrics));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadHealth() {
    setBusy(true);
    try {
      const [t, runs, cov] = await Promise.all([getIngestTrust(), getIngestRuns(), getCompleteness()]);
      setTrust(t);
      setIngestRuns(Array.isArray(runs) ? runs : []);
      setCompleteness(cov);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadInventory(status?: string) {
    setBusy(true);
    try {
      setInventory(await getInventoryItems({ status: status || undefined }));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void loadOverview();
  }, []);

  function openObject(obj: ContextObject) {
    if (obj.type === "Item") {
      setSplit(false);
      void loadItem(obj.id, { view: "inventory" });
    }
  }

  function askAboutItem(id: string) {
    const q = "Should I review the price of this listing?";
    setSku(id);
    setQuestion(q);
    setSplit(true);
    setView("librarian");
    void runQuestion(q, id);
    if (!item) void loadItem(id, { view: "librarian", split: true });
  }

  function go(next: View) {
    setView(next);
    if (next !== "librarian") setSplit(false);
    if (next === "inventory") {
      setShowObject(false);
      if (!inventory.length) void loadInventory();
    }
    if (next === "overview" && !snapshot) void loadOverview();
    if (next === "eval" && !evalReport) void runEval();
    if (next === "health" && !trust) void loadHealth();
  }

  const env = runtime?.environment || "demo";
  const model = runtime?.model;
  const modelKind = model?.kind || "fake";
  const modelLabel =
    modelKind === "fake"
      ? `Fake / Test · ${model?.model || "fake"}`
      : modelKind === "local"
        ? `Local · ${model?.model || "local"}`
        : `Remote · ${model?.model || "model"}`;
  const asOf = String(snapshot?.provenance?.as_of || runtime?.as_of || "");
  const attentionRow: AttentionQueueRow | null = useMemo(() => {
    if (!sku) return null;
    return attention?.data?.queue?.find((row) => row.sku === sku) || null;
  }, [attention, sku]);
  const boundLabel = sku && item ? productName(item.data?.item, sku) : sku;
  const pageTitle = NAV.find((n) => n.id === view)?.label || "Workspace";
  const objectOpen = showObject && item && (view === "inventory" || (view === "librarian" && split));

  return (
    <div className="workspace">
      <aside className="nav">
        <div className="brand">
          <div className="brand-kicker">Commerce</div>
          <div className="brand-name">Data Platform</div>
        </div>
        <nav className="nav-list">
          {NAV.map((n) => (
            <button
              key={n.id}
              className={`nav-item ${view === n.id ? "active" : ""}`}
              data-testid={`nav-${n.id}`}
              onClick={() => go(n.id)}
            >
              {n.label}
            </button>
          ))}
        </nav>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="topbar-title">{pageTitle}</div>
          <div className="topbar-meta">
            {busy || askBusy ? <span className="busy-dot">Loading</span> : null}
            {asOf ? <span>as of {observedDate(asOf) || asOf.slice(0, 10)}</span> : null}
            <div className={`env-badge env-${env}`} data-testid="environment">
              {env === "private" ? "PRIVATE · LOCAL" : env === "heldout" ? "HELD OUT · EVALUATION" : "DEMO · SYNTHETIC"}
            </div>
            <div
              className={`env-badge model-${modelKind}`}
              data-testid="model-status"
              title={model?.real ? "Configured model" : "Not a real model"}
            >
              {modelLabel}
            </div>
          </div>
        </header>
        {error && <p className="err">{error}</p>}
        <div className={`content ${view === "librarian" && split && item ? "split" : ""}`}>
          {view === "overview" && (
            <OverviewPage
              snapshot={snapshot}
              attention={attention}
              changes={changes}
              loading={busy && !snapshot}
              onOpenSku={(id) => void loadItem(id, { view: "inventory" })}
            />
          )}
          {view === "inventory" && !objectOpen && (
            <InventoryPage
              inventory={inventory}
              invFilter={invFilter}
              setFilter={(st) => {
                setInvFilter(st);
                void loadInventory(st);
              }}
              selectedSku={sku || undefined}
              onOpen={(id) => void loadItem(id, { view: "inventory" })}
            />
          )}
          {view === "inventory" && objectOpen && item && (
            <ObjectView
              item={item}
              history={history}
              attention={attentionRow}
              onBack={() => {
                setShowObject(false);
                if (!inventory.length) void loadInventory();
              }}
              onAskLibrarian={askAboutItem}
              onReload={() => sku && void loadItem(sku)}
            />
          )}
          {view === "librarian" && split && item && (
            <ObjectView
              item={item}
              history={history}
              attention={attentionRow}
              compact
              onAskLibrarian={askAboutItem}
              onReload={() => sku && void loadItem(sku)}
            />
          )}
          {view === "librarian" && (
            <LibrarianPage
              question={question}
              setQuestion={setQuestion}
              bundle={bundle}
              answer={answer}
              busy={askBusy}
              boundLabel={split ? boundLabel : null}
              onAsk={(q) => void runQuestion(q, split ? sku || undefined : undefined)}
              onOpenObject={openObject}
            />
          )}
          {view === "eval" && (
            <EvaluationPage
              evalReport={evalReport}
              compare={compare}
              answers={answers}
              planEval={planEval}
              librarianEval={librarianEval}
              busy={busy}
              onRerun={() => void runEval()}
              onOpenQuestion={(q) => {
                setQuestion(q);
                setSplit(false);
                setView("librarian");
                void runQuestion(q);
              }}
            />
          )}
          {view === "health" && (
            <HealthPage trust={trust} ingestRuns={ingestRuns} completeness={completeness} runtime={runtime} />
          )}
        </div>
      </div>
    </div>
  );
}
