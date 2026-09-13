import { useEffect, useState } from "react";
import {
  getAttention,
  getCompleteness,
  getEval,
  getEvalAnswers,
  getEvalAnalyst,
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
import { ContextPage } from "./ContextPage";
import { EvaluationPage } from "./EvaluationPage";
import { HealthPage } from "./HealthPage";
import { InventoryPage } from "./InventoryPage";
import { OverviewPage } from "./OverviewPage";
import type { ContextBundle, ContextObject, InventoryRow, RuntimeInfo, Tab } from "./types";

export default function App() {
  const [tab, setTab] = useState<Tab>("overview");
  const [question, setQuestion] = useState("Should I reprice j4-military-s?");
  const [bundle, setBundle] = useState<ContextBundle | null>(null);
  const [evalReport, setEvalReport] = useState<any>(null);
  const [compare, setCompare] = useState<any>(null);
  const [answers, setAnswers] = useState<any>(null);
  const [planEval, setPlanEval] = useState<any>(null);
  const [analystEval, setAnalystEval] = useState<any>(null);
  const [sku, setSku] = useState("j4-military-s");
  const [item, setItem] = useState<any>(null);
  const [history, setHistory] = useState<any>(null);
  const [answer, setAnswer] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [askBusy, setAskBusy] = useState(false);
  const [snapshot, setSnapshot] = useState<any>(null);
  const [attention, setAttention] = useState<any>(null);
  const [inventory, setInventory] = useState<InventoryRow[]>([]);
  const [invFilter, setInvFilter] = useState("");
  const [trust, setTrust] = useState<any>(null);
  const [ingestRuns, setIngestRuns] = useState<any[]>([]);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [completeness, setCompleteness] = useState<any>(null);

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
      const [engine, cmp, ans, plan, analyst] = await Promise.all([
        getEval(),
        getEvalCompare(),
        getEvalAnswers(),
        getEvalPlan(),
        getEvalAnalyst(),
      ]);
      setEvalReport(engine);
      setCompare(cmp);
      setAnswers(ans);
      setPlanEval(plan);
      setAnalystEval(analyst);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadItem(id: string, opts?: { switchTab?: boolean }) {
    setBusy(true);
    setError(null);
    try {
      const [it, hist] = await Promise.all([getItem(id), getItemHistory(id)]);
      setItem(it);
      setHistory(hist);
      setSku(id);
      if (opts?.switchTab !== false) setTab("inventory");
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadOverview() {
    setBusy(true);
    try {
      const [snap, att, rt] = await Promise.all([getSnapshot(), getAttention(), getRuntime()]);
      setSnapshot(snap);
      setAttention(att);
      setRuntime(rt);
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
    void runQuestion("Should I reprice j4-military-s?");
  }, []);

  function openObject(obj: ContextObject) {
    if (obj.type === "Item") void loadItem(obj.id);
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

  return (
    <div className="app">
      <header className="shell">
        <div>
          <h1>Commerce Data Platform</h1>
          <p className="lede">Operational workspace for resale context and sandbox decisions.</p>
        </div>
        <div className="badges">
          <div className={`env-badge env-${env}`} data-testid="environment">
            {env === "private" ? "PRIVATE · LOCAL" : env === "heldout" ? "HELD OUT · EVALUATION" : "DEMO · SYNTHETIC"}
          </div>
          <div className={`env-badge model-${modelKind}`} data-testid="model-status" title={model?.real ? "Configured model" : "Not a real model"}>
            {modelLabel}
          </div>
        </div>
      </header>
      <div className="tabs">
        <button className={tab === "overview" ? "active" : ""} onClick={() => { setTab("overview"); if (!snapshot) void loadOverview(); }}>Overview</button>
        <button className={tab === "inventory" ? "active" : ""} onClick={() => { setTab("inventory"); if (!inventory.length) void loadInventory(); }}>Inventory</button>
        <button className={tab === "context" ? "active" : ""} onClick={() => setTab("context")}>Context</button>
        <button className={tab === "eval" ? "active" : ""} onClick={() => { setTab("eval"); if (!evalReport) void runEval(); }}>Evaluation</button>
        <button className={tab === "health" ? "active" : ""} onClick={() => { setTab("health"); if (!trust) void loadHealth(); }}>Data Health</button>
      </div>
      {error && <p className="err">{error}</p>}

      {tab === "overview" && (
        <OverviewPage snapshot={snapshot} attention={attention} onOpenSku={(id) => void loadItem(id)} />
      )}
      {tab === "inventory" && (
        <InventoryPage
          sku={sku}
          setSku={setSku}
          inventory={inventory}
          invFilter={invFilter}
          setFilter={(st) => { setInvFilter(st); void loadInventory(st); }}
          item={item}
          history={history}
          onLoad={(id) => void loadItem(id)}
          onReloadItem={() => void loadItem(sku, { switchTab: false })}
          onAskItem={(id) => {
            const q = `Should I reprice ${id}?`;
            setSku(id);
            setQuestion(q);
            setTab("context");
            void runQuestion(q, id);
          }}
        />
      )}
      {tab === "context" && (
        <ContextPage
          question={question}
          setQuestion={setQuestion}
          bundle={bundle}
          answer={answer}
          busy={askBusy}
          onAsk={(q) => void runQuestion(q)}
          onOpenObject={openObject}
        />
      )}
      {tab === "eval" && (
        <EvaluationPage
          evalReport={evalReport}
          compare={compare}
          answers={answers}
          planEval={planEval}
          analystEval={analystEval}
          busy={busy}
          onRerun={() => void runEval()}
          onOpenQuestion={(q) => { setQuestion(q); setTab("context"); void runQuestion(q); }}
        />
      )}
      {tab === "health" && (
        <HealthPage trust={trust} ingestRuns={ingestRuns} completeness={completeness} runtime={runtime} />
      )}
      {sku && tab === "context" && (
        <div className="ask-item">
          <button
            className="chip"
            onClick={() => {
              const q = `Should I reprice ${sku}?`;
              setQuestion(q);
              void runQuestion(q, sku);
            }}
          >
            Ask about {sku}
          </button>
        </div>
      )}
    </div>
  );
}
