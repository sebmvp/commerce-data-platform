import type {
  ActionRecord,
  AnalystResponse,
  AttentionQueue,
  BusinessSnapshot,
  CompletenessReport,
  ContextBundle,
  EvalLayerReport,
  IngestRun,
  InventoryRow,
  ItemHistory,
  ItemPayload,
  RuntimeInfo,
  TrustReport,
} from "./types";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<T>;
}

async function sendJson<T>(path: string, body: unknown, method = "POST"): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<T>;
}

export async function getContext(question: string, sku?: string): Promise<ContextBundle> {
  const url = new URL("/context", API);
  url.searchParams.set("question", question);
  if (sku) url.searchParams.set("sku", sku);
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<ContextBundle>;
}

export async function postAnswer(
  question: string,
  sku?: string,
  asOf?: string,
): Promise<AnalystResponse> {
  return sendJson<AnalystResponse>("/answer", {
    question,
    sku: sku || undefined,
    as_of: asOf || undefined,
  });
}

export const getEval = () => getJson<EvalLayerReport>("/eval");
export const getEvalCompare = () => getJson<EvalLayerReport>("/eval/compare");
export const getEvalAnswers = () => getJson<EvalLayerReport>("/eval/answers");
export const getEvalPlan = () => getJson<EvalLayerReport>("/eval/plan");
export const getEvalAnalyst = () => getJson<EvalLayerReport>("/eval/analyst");
export const getItem = (sku: string) =>
  getJson<ItemPayload>(`/business/items/${encodeURIComponent(sku)}`);
export const getItemHistory = (sku: string) =>
  getJson<ItemHistory>(`/business/items/${encodeURIComponent(sku)}/history`);
export const getSnapshot = () => getJson<BusinessSnapshot>("/business/snapshot");
export const getAttention = () => getJson<AttentionQueue>("/business/attention");
export const getIngestTrust = () => getJson<TrustReport>("/ingest/trust");
export const getIngestRuns = () => getJson<IngestRun[]>("/ingest/runs");
export const getRuntime = () => getJson<RuntimeInfo>("/runtime");
export const getCompleteness = () => getJson<CompletenessReport>("/completeness");
export const getSuggestAction = (sku: string) =>
  getJson<{ data?: Record<string, unknown> }>(
    `/business/items/${encodeURIComponent(sku)}/suggest-action`,
  );

export function getInventoryItems(opts?: {
  status?: string;
  listed?: string;
  missing_cost?: boolean;
}) {
  const q = new URLSearchParams();
  if (opts?.status) q.set("status", opts.status);
  if (opts?.listed) q.set("listed", opts.listed);
  if (opts?.missing_cost) q.set("missing_cost", "true");
  const suffix = q.toString() ? `?${q}` : "";
  return getJson<InventoryRow[]>(`/inventory/items${suffix}`);
}

export function proposeAction(body: Record<string, unknown>) {
  return sendJson<{ data?: ActionRecord } & ActionRecord>("/business/actions", body);
}

export function approveAction(id: string) {
  return sendJson(`/business/actions/${id}/approve`, { actor: "operator" });
}

export function rejectAction(id: string, reason?: string) {
  return sendJson(`/business/actions/${id}/reject`, {
    actor: "operator",
    reason,
  });
}

export function listActions(targetId?: string) {
  const q = targetId ? `?target_id=${encodeURIComponent(targetId)}` : "";
  return getJson<{ data?: { actions?: ActionRecord[] } }>(`/business/actions${q}`);
}
