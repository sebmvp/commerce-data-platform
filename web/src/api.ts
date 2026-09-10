const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function getJson(path: string) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function sendJson(path: string, body: unknown, method = "POST") {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getContext(question: string, sku?: string) {
  const url = new URL("/context", API);
  url.searchParams.set("question", question);
  if (sku) url.searchParams.set("sku", sku);
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getAnswer(question: string, sku?: string) {
  const url = new URL("/answer", API);
  url.searchParams.set("question", question);
  if (sku) url.searchParams.set("sku", sku);
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export const getEval = () => getJson("/eval");
export const getEvalCompare = () => getJson("/eval/compare");
export const getItem = (sku: string) =>
  getJson(`/business/items/${encodeURIComponent(sku)}`);
export const getItemHistory = (sku: string) =>
  getJson(`/business/items/${encodeURIComponent(sku)}/history`);
export const getSnapshot = () => getJson("/business/snapshot");
export const getAttention = () => getJson("/business/attention");
export const getIngestTrust = () => getJson("/ingest/trust");
export const getIngestRuns = () => getJson("/ingest/runs");
export const getRuntime = () => getJson("/runtime");
export const getCompleteness = () => getJson("/completeness");
export const getSuggestAction = (sku: string) =>
  getJson(`/business/items/${encodeURIComponent(sku)}/suggest-action`);

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
  return getJson(`/inventory/items${suffix}`);
}

export function proposeAction(body: Record<string, unknown>) {
  return sendJson("/business/actions", body);
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
  return getJson(`/business/actions${q}`);
}
