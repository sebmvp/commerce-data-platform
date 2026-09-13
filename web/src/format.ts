import type {
  AttentionQueueRow,
  ContextBundle,
  ContextObject,
  EvidenceUnit,
  LibrarianResponse,
} from "./types";

const LABEL: Record<string, string> = {
  watch_rate: "Watch rate",
  listing_age_days: "Listing age",
  inventory_age_days: "Inventory age",
  asking_price_usd: "Asking price",
  price_usd: "Price",
  acquisition_cost_cny: "Acquisition",
  target_price_usd: "Target price",
  watchers: "Watchers",
  offers: "Offers",
  views: "Views",
  listed_at: "Listed",
  status: "Status",
  platform: "Channel",
  listing_as_of: "Listing as-of",
  item_status: "Lifecycle",
  has_active_listing: "Active listing",
  listing_count: "Listings",
  owned_unlisted: "Unlisted",
  listed_items: "Listed",
  sold_items: "Sold",
  items_total: "Items",
  capital_tied_up_cny: "Capital tied up",
  capital_items: "Items holding capital",
  active_listings: "Active listings",
  stale_active_listings: "Stale listings",
  orders: "Orders",
  realized_revenue_usd: "Realized revenue",
  realized_gross_after_fees_usd: "Gross after fees",
  listing_events_in_window: "Listing events",
  item_events_in_window: "Item events",
  lookback_days: "Lookback",
  changed_metric_count: "Changed measures",
};

const WHY_TERMS: Record<string, string> = {
  reprice_item: "Price review",
  item_state: "item state",
  listing_age: "listing age",
  asking_price: "asking price",
  acquisition_cost: "acquisition cost",
  item_history: "item history",
  repricing_policy: "repricing policy",
  listing_performance: "listing performance",
  channel_as_of: "channel as-of",
  recent_changes: "recent changes",
  previous_snapshot: "a prior snapshot",
};

const TECHNICAL_LABELS = new Set([
  "sku",
  "has active listing",
  "listing count",
  "item status",
  "status",
]);

export interface EvidenceCard {
  label: string;
  value: string;
  source?: string | null;
  observed?: string | null;
  ref?: string;
}

export function humanLabel(raw: string): string {
  if (LABEL[raw]) return LABEL[raw];
  const trimmed = raw.replace(/^(fact|metric|object|event|rule|note):/, "");
  if (LABEL[trimmed]) return LABEL[trimmed];
  const last = trimmed.includes(":") ? trimmed.slice(trimmed.lastIndexOf(":") + 1) : trimmed;
  if (LABEL[last]) return LABEL[last];
  return last.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatEvidenceValue(value: unknown, key?: string): string | null {
  if (value == null || value === "") return null;
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "number") {
    if (key && /(_usd|_cny|price|cost|revenue|capital_tied)/i.test(key) && !/age|days|rate|count/i.test(key)) {
      return key.toLowerCase().includes("cny") ? formatMoney(value, "CNY") : formatMoney(value, "USD");
    }
    if (key && /rate/i.test(key) && value > 0 && value < 1) return `${(value * 100).toFixed(1)}%`;
    if (value > 0 && value < 1) return `${(value * 100).toFixed(1)}%`;
    if (key && /age|days/i.test(key)) return formatDays(value);
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  if (typeof value === "object") return null;
  return String(value);
}

export function formatMoney(value: unknown, currency: "USD" | "CNY"): string {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  const body = n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  return currency === "USD" ? `$${body}` : `${body} CNY`;
}

export function formatDays(value: unknown, noun = "days"): string {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  return `${n} ${noun}`;
}

export function observedDate(iso?: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return iso;
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${months[Number(m[2]) - 1]} ${Number(m[3])}`;
  }
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function parseRef(ref: string): { type: string; id: string } {
  const idx = ref.indexOf(":");
  if (idx === -1) return { type: ref, id: "" };
  return { type: ref.slice(0, idx), id: ref.slice(idx + 1) };
}

export function typeLabel(type: string): string {
  if (type === "EngagementObservation") return "Engagement";
  if (type === "BusinessSnapshot") return "Snapshot";
  return type;
}

export function formatChannel(value: unknown): string {
  const s = String(value || "").trim();
  if (!s) return "—";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function itemLabel(obj: ContextObject): string {
  const props = obj.properties || {};
  if (obj.type === "Item") return String(props.product || obj.id);
  if (obj.type === "Listing") {
    return `${formatChannel(props.platform || "listing")} listing`;
  }
  if (obj.type === "Channel") return formatChannel(props.platform || obj.id);
  if (obj.type === "Order") return "Order";
  if (obj.type === "Recommendation") return "Recommendation";
  if (obj.type === "EngagementObservation") return "Engagement";
  if (obj.type === "IngestRun") return "Ingest";
  return typeLabel(obj.type);
}

export function objectLabel(objects: ContextObject[], ref: string): string {
  const { type, id } = parseRef(ref);
  const obj = objects.find((o) => o.type === type && String(o.id) === id);
  if (obj) return itemLabel(obj);
  if (type === "Item") return id;
  if (type === "Listing") return "Listing";
  if (type === "EngagementObservation") return "Engagement";
  return typeLabel(type);
}

export function relVerb(type: string): string {
  const map: Record<string, string> = {
    HAS_LISTING: "listed",
    ON_CHANNEL: "on",
    HAS_ENGAGEMENT: "engagement",
    RESULTED_IN: "sold as",
    TARGETS: "targets",
    PRECEDES: "then",
  };
  return map[type] || type.toLowerCase().replace(/_/g, " ");
}

export function attentionAction(reason?: string | null): string {
  switch (reason) {
    case "unlisted_owned":
      return "List suggested";
    case "stale_listing":
    case "high_attention_no_offers":
      return "Price review suggested";
    case "listed_active":
      return "Monitor";
    default:
      return reason ? humanLabel(reason) : "Review";
  }
}

export function attentionMeta(row: AttentionQueueRow): string {
  if (row.item_status === "owned" || row.attention_reason === "unlisted_owned") {
    const age = row.inventory_age_days;
    return age != null ? `Unlisted · ${age} days` : "Unlisted";
  }
  const bits: string[] = [];
  if (row.listing_age_days != null) bits.push(`Listed ${row.listing_age_days} days`);
  if (row.watchers != null) bits.push(`${row.watchers} watchers`);
  if (row.offers != null) bits.push(`${row.offers} offers`);
  return bits.join(" · ") || "Listed";
}

export function evidenceObjectCaption(
  unit: EvidenceUnit,
  bundle: ContextBundle | null,
): string | null {
  if (!unit.object_ref) return null;
  if (!bundle) return null;
  return objectLabel(bundle.objects, unit.object_ref);
}

export function kv(value: unknown): string {
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

export function productName(item: Record<string, unknown> | undefined, fallback = "Item"): string {
  if (!item) return fallback;
  return String(item.product || item.sku || fallback);
}

export function eventLabel(type: unknown): string {
  const raw = String(type || "event");
  if (/listing.?price.?change/i.test(raw) || /price.?change/i.test(raw)) return "Price change";
  if (/listing.?opened/i.test(raw)) return "Listing opened";
  return humanLabel(raw);
}

export function formatWhy(why: string): string {
  if (!why) return "";
  return why.replace(/[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+/g, (token) => {
    if (WHY_TERMS[token]) return WHY_TERMS[token];
    return humanLabel(token).toLowerCase();
  });
}

export function listingFromBundle(bundle: ContextBundle | null): ContextObject | undefined {
  return bundle?.objects.find((o) => o.type === "Listing");
}

export function itemFromBundle(bundle: ContextBundle | null): ContextObject | undefined {
  return bundle?.objects.find((o) => o.type === "Item");
}

function pushCard(
  cards: EvidenceCard[],
  seen: Set<string>,
  card: EvidenceCard,
) {
  const key = card.label.toLowerCase();
  if (seen.has(key) || !card.value) return;
  seen.add(key);
  cards.push(card);
}

export function decisiveCards(
  answer: LibrarianResponse | null,
  bundle: ContextBundle | null,
): EvidenceCard[] {
  if (!bundle) return [];
  const cards: EvidenceCard[] = [];
  const seen = new Set<string>();
  const listing = listingFromBundle(bundle);
  const item = itemFromBundle(bundle);
  const source = listing
    ? `${formatChannel(listing.properties?.platform)} listing`
    : item
      ? itemLabel(item)
      : null;
  const observed = observedDate(bundle.as_of);

  const preferred: Array<[string, unknown]> = [
    ["watch_rate", bundle.metrics?.watch_rate ?? listing?.properties?.watch_rate],
    ["listing_age_days", bundle.metrics?.listing_age_days ?? listing?.properties?.listing_age_days],
    ["asking_price_usd", bundle.metrics?.asking_price_usd ?? listing?.properties?.price_usd],
    ["watchers", listing?.properties?.watchers],
    ["offers", listing?.properties?.offers],
    ["views", listing?.properties?.views],
    ["acquisition_cost_cny", bundle.metrics?.acquisition_cost_cny ?? item?.properties?.acquisition_cost_cny],
    ["inventory_age_days", bundle.metrics?.inventory_age_days],
  ];
  for (const [key, value] of preferred) {
    const formatted = formatEvidenceValue(value, key);
    if (!formatted) continue;
    pushCard(cards, seen, {
      label: humanLabel(key),
      value: formatted,
      source,
      observed,
    });
  }

  if (cards.length >= 4) return cards.slice(0, 6);

  const units = [
    ...(answer?.evidence?.evidence_units || []),
    ...(bundle.evidence_units || []),
  ];
  const byRef = new Map(units.map((unit) => [unit.ref, unit]));
  const cited = (answer?.evidence_refs || [])
    .map((ref) => byRef.get(ref) || { ref, kind: "unknown", label: ref })
    .filter((unit) => {
      const label = humanLabel(unit.label).toLowerCase();
      if (unit.kind === "object") return false;
      if (TECHNICAL_LABELS.has(label)) return false;
      if (typeof unit.value === "boolean") return false;
      return formatEvidenceValue(unit.value, unit.label) != null;
    });
  for (const unit of cited) {
    const formatted = formatEvidenceValue(unit.value, unit.label);
    if (!formatted) continue;
    pushCard(cards, seen, {
      label: humanLabel(unit.label),
      value: formatted,
      source: evidenceObjectCaption(unit, bundle) || source,
      observed,
      ref: unit.ref,
    });
  }
  return cards.slice(0, 6);
}

export function collapseTimeline<T extends { type?: unknown; at?: unknown }>(events: T[]): T[] {
  const out: T[] = [];
  const seen = new Set<string>();
  for (const event of events) {
    const day = observedDate(String(event.at || "")) || "";
    const raw = String(event.type || "");
    const kind = /price/i.test(raw) ? "price" : raw.toLowerCase();
    const key = `${day}:${kind}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(event);
  }
  return out;
}

export function parseSnapshotDeltas(
  facts: Record<string, unknown> | undefined,
  metrics?: Record<string, unknown>,
): Array<{ label: string; detail: string }> {
  const rows: Array<{ label: string; detail: string }> = [];
  const deltas = facts?.deltas;
  if (deltas && typeof deltas === "object") {
    for (const [key, raw] of Object.entries(deltas as Record<string, { from?: unknown; to?: unknown; delta?: number }>)) {
      const from = formatEvidenceValue(raw.from, key) ?? kv(raw.from);
      const to = formatEvidenceValue(raw.to, key) ?? kv(raw.to);
      rows.push({ label: humanLabel(key), detail: `${from} → ${to}` });
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

export function rankAttention(queue: AttentionQueueRow[]): AttentionQueueRow[] {
  const review: AttentionQueueRow[] = [];
  const monitor: AttentionQueueRow[] = [];
  const unlisted: AttentionQueueRow[] = [];
  for (const row of queue) {
    if (row.attention_reason === "unlisted_owned") unlisted.push(row);
    else if (row.attention_reason === "listed_active") monitor.push(row);
    else review.push(row);
  }
  const shown: AttentionQueueRow[] = [];
  shown.push(...review.slice(0, 6));
  shown.push(...monitor.slice(0, 2));
  const remaining = Math.max(4, 12 - shown.length);
  shown.push(...unlisted.slice(0, remaining));
  return shown;
}
