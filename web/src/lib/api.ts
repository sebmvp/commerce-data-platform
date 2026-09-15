import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  ActionRecord,
  AttentionQueue,
  BusinessSnapshot,
  CompletenessReport,
  ContextBundle,
  EvalLayerReport,
  IngestRun,
  InventoryRow,
  ItemHistory,
  ItemPayload,
  LibrarianResponse,
  RuntimeInfo,
  TrustReport,
} from "@/types";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) {
    throw new Error(
      `${res.status} ${res.statusText} — ${truncate(await res.text())}`,
    );
  }
  return (await res.json()) as T;
}

function truncate(text: string): string {
  return text.length > 300 ? `${text.slice(0, 300)}…` : text;
}

async function sendJson<T>(path: string, body: unknown, method = "POST"): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(
      `${res.status} ${res.statusText} — ${truncate(await res.text())}`,
    );
  }
  return (await res.json()) as T;
}

/* ── plain fetchers (router loaders + query fns share these) ── */

export const fetchContext = (question: string, sku?: string) => {
  const url = new URL("/context", API);
  url.searchParams.set("question", question);
  if (sku) url.searchParams.set("sku", sku);
  return fetch(url).then(async (res) => {
    if (!res.ok) throw new Error(await res.text());
    return (await res.json()) as ContextBundle;
  });
};

export const fetchItem = (sku: string) =>
  getJson<ItemPayload>(`/business/items/${encodeURIComponent(sku)}`);
export const fetchItemHistory = (sku: string) =>
  getJson<ItemHistory>(`/business/items/${encodeURIComponent(sku)}/history`);

/* ── query keys / hooks ── */

export const keys = {
  runtime: ["runtime"] as const,
  snapshot: ["snapshot"] as const,
  attention: ["attention"] as const,
  changes: ["changes"] as const,
  inventory: (status?: string) => ["inventory", status ?? "all"] as const,
  item: (sku: string) => ["item", sku] as const,
  history: (sku: string) => ["history", sku] as const,
  coreEvals: () =>
    [
      ["coreEval"],
      ["evalCompare"],
      ["evalAnswers"],
      ["evalPlan"],
      ["evalLibrarian"],
    ] as const,
};

export function useRuntime() {
  return useQuery<RuntimeInfo>({
    queryKey: keys.runtime,
    queryFn: () => getJson("/runtime"),
    staleTime: 60_000,
  });
}

export function useRuntimeValue(): RuntimeInfo | undefined {
  return useRuntime().data;
}

export function useSnapshot() {
  return useQuery<BusinessSnapshot>({
    queryKey: keys.snapshot,
    queryFn: () => getJson("/business/snapshot"),
  });
}

export function useAttention() {
  return useQuery<AttentionQueue>({
    queryKey: keys.attention,
    queryFn: () => getJson("/business/attention"),
  });
}

export function useRecentChanges() {
  return useQuery<Array<{ label: string; detail: string }> | null>({
    queryKey: keys.changes,
    queryFn: async () => {
      const bundle = await getJson<ContextBundle>(
        `/context?question=${encodeURIComponent("What changed since the previous snapshot?")}`,
      );
      return parseSnapshotDeltas(bundle.facts, bundle.metrics);
    },
    retry: 1,
  });
}

function parseSnapshotDeltas(
  facts: Record<string, unknown> | undefined,
  metrics?: Record<string, unknown>,
): Array<{ label: string; detail: string }> {
  const rows: Array<{ label: string; detail: string }> = [];
  const deltas = facts?.deltas;
  if (deltas && typeof deltas === "object") {
    for (const [key, raw] of Object.entries(
      deltas as Record<string, { from?: unknown; to?: unknown }>,
    )) {
      const from = fmt(raw.from) ?? "—";
      const to = fmt(raw.to) ?? "—";
      rows.push({ label: human(key), detail: `${from} → ${to}` });
    }
  }
  if (!rows.length && metrics) {
    const listingN = metrics.listing_events_in_window;
    const itemN = metrics.item_events_in_window;
    const days = metrics.lookback_days;
    if (listingN != null || itemN != null) {
      rows.push({
        label: days != null ? `Last ${days} days` : "Activity",
        detail: `${listingN ?? 0} listing events · ${itemN ?? 0} item events`,
      });
    }
  }
  return rows.slice(0, 6);
}

function fmt(value: unknown): string | null {
  if (value == null || value === "") return null;
  if (typeof value === "number") {
    return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
  }
  return String(value);
}

function human(raw: string): string {
  const SPECIAL: Record<string, string> = {
    capital_tied_up_cny: "Capital tied up (CNY)",
    capital_tied_up_usd_est: "Capital tied up (USD est.)",
    items_total: "Items",
    listed_items: "Listed items",
    sold_items: "Sold items",
    owned_unlisted: "Unlisted (owned)",
    active_listings: "Active listings",
    stale_active_listings: "Stale listings",
    capital_items: "Items holding capital",
  };
  if (SPECIAL[raw]) return SPECIAL[raw];
  return raw
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function useInventory(status?: string) {
  const suffix = status ? `?status=${encodeURIComponent(status)}` : "";
  return useQuery<InventoryRow[]>({
    queryKey: keys.inventory(status),
    queryFn: () => getJson(`/inventory/items${suffix}`),
  });
}

export function useItem(sku: string | null | undefined) {
  return useQuery<ItemPayload>({
    queryKey: keys.item(sku || "—"),
    queryFn: () => fetchItem(sku as string),
    enabled: !!sku,
    retry: false,
  });
}

export function useItemHistory(sku: string | null | undefined) {
  return useQuery<ItemHistory>({
    queryKey: keys.history(sku || "—"),
    queryFn: () => fetchItemHistory(sku as string),
    enabled: !!sku,
  });
}

export function useEvalLayers() {
  const core = useQuery<EvalLayerReport>({
    queryKey: ["coreEval"],
    queryFn: () => getJson("/eval"),
  });
  const compare = useQuery<EvalLayerReport | null>({
    queryKey: ["evalCompare"],
    queryFn: () => getJson("/eval/compare"),
  });
  const answers = useQuery<EvalLayerReport>({
    queryKey: ["evalAnswers"],
    queryFn: () => getJson("/eval/answers"),
  });
  const plan = useQuery<EvalLayerReport>({
    queryKey: ["evalPlan"],
    queryFn: () => getJson("/eval/plan"),
  });
  const librarian = useQuery<EvalLayerReport>({
    queryKey: ["evalLibrarian"],
    queryFn: () => getJson("/eval/librarian"),
  });
  const layers = [core, compare, answers, plan, librarian];
  const loading = layers.some((q) => q.isPending);
  const error = layers.find((q) => q.isError)?.error;
  return { core, compare, answers, plan, librarian, loading, error };
}

export function useTrust() {
  return useQuery<TrustReport>({
    queryKey: ["trust"],
    queryFn: () => getJson("/ingest/trust"),
  });
}

export function useIngestRuns() {
  return useQuery<IngestRun[]>({
    queryKey: ["ingestRuns"],
    queryFn: () => getJson("/ingest/runs"),
  });
}

export function useCompleteness() {
  return useQuery<CompletenessReport>({
    queryKey: ["completeness"],
    queryFn: () => getJson("/completeness"),
  });
}

/* ── mutations ── */

export function useAskLibrarian() {
  return useMutation({
    mutationFn: async (vars: { question: string; sku?: string }) =>
      sendJson<LibrarianResponse>("/answer", {
        question: vars.question,
        sku: vars.sku || undefined,
      }),
  });
}

export function useActionInvalidation() {
  const qc = useQueryClient();
  return (sku?: string) => {
    void qc.invalidateQueries({ queryKey: keys.item(sku || "—") });
    void qc.invalidateQueries({ queryKey: keys.history(sku || "—") });
    void qc.invalidateQueries({ queryKey: keys.attention });
    void qc.invalidateQueries({ queryKey: keys.snapshot });
    void qc.invalidateQueries({ queryKey: ["actions"] });
  };
}

export function useListActions(sku: string | null) {
  return useQuery<{ data?: { actions?: ActionRecord[] } }>({
    queryKey: ["actions", sku],
    queryFn: () =>
      getJson(`/business/actions?target_id=${encodeURIComponent(sku as string)}`),
    enabled: !!sku,
  });
}

export function useSuggestAction(sku: string | null) {
  return useQuery<{ data?: Record<string, unknown> }>({
    queryKey: ["suggestAction", sku],
    queryFn: () =>
      getJson(
        `/business/items/${encodeURIComponent(sku as string)}/suggest-action`,
      ),
    enabled: !!sku,
  });
}

export function useProposeAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      sendJson<{ data?: ActionRecord } & ActionRecord>("/business/actions", body),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({
        queryKey: ["actions", (variables as { target_id?: string }).target_id],
      });
    },
  });
}

export function useDecideAction() {
  const qc = useQueryClient();
  const invalidateActionState = useActionInvalidation();
  return useMutation({
    mutationFn: (vars: {
      actionId: string;
      kind: "approve" | "reject";
      reason?: string;
    }) =>
      sendJson(
        `/business/actions/${vars.actionId}/${vars.kind}`,
        { actor: "operator", reason: vars.reason },
      ),
    onSuccess: (_d, vars) => {
      const sku = vars.actionId;
      void qc.invalidateQueries({ queryKey: ["actions"] });
      void qc.invalidateQueries({ queryKey: keys.item(sku) });
      void qc.invalidateQueries({ queryKey: keys.history(sku) });
      void qc.invalidateQueries({ queryKey: keys.attention });
      void qc.invalidateQueries({ queryKey: keys.snapshot });
      invalidateActionState();
    },
  });
}
