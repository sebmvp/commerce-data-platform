/**
 * Formatting helpers. Kept framework-free so both React pages and tests
 * can import them.
 */
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
    const months = [
      "Jan", "Feb", "Mar", "Apr", "May", "Jun",
      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ];
    return `${months[Number(m[2]) - 1]} ${Number(m[3])}`;
  }
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function humanLabel(raw: string): string {
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
    reprice_item: "Reprice item",
    explain_attention: "Explain attention",
    item_state: "Item state",
  };
  if (LABEL[raw]) return LABEL[raw];
  const trimmed = raw.replace(/^(fact|metric|object|event|rule|note):/, "");
  if (LABEL[trimmed]) return LABEL[trimmed];
  const last = trimmed.includes(":")
    ? trimmed.slice(trimmed.lastIndexOf(":") + 1)
    : trimmed;
  if (LABEL[last]) return LABEL[last];
  return last.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatEvidenceValue(value: unknown, key?: string): string | null {
  if (value == null || value === "") return null;
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "number") {
    if (
      key &&
      /(_usd|_cny|price|cost|revenue|capital_tied)/i.test(key) &&
      !/age|days|rate|count/i.test(key)
    ) {
      return key.toLowerCase().includes("cny")
        ? formatMoney(value, "CNY")
        : formatMoney(value, "USD");
    }
    if (key && /rate/i.test(key) && value > 0 && value < 1) {
      return `${(value * 100).toFixed(1)}%`;
    }
    if (key && /age|days/i.test(key)) return formatDays(value);
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  if (typeof value === "object") return null;
  return String(value);
}

export function productName(
  item: Record<string, unknown> | undefined,
  fallback = "Item",
): string {
  if (!item) return fallback;
  return String(item.product || item.sku || fallback);
}

export interface EvidenceCard {
  label: string;
  value: string;
  source?: string | null;
  observed?: string | null;
  ref?: string;
}

export interface MinimalBundle {
  question?: string;
  as_of?: string;
  objects?: Array<{ type: string; id: string; properties?: Record<string, unknown> }>;
  metrics?: Record<string, unknown>;
}

export interface MinimalAnswer {
  evidence_refs?: string[];
  evidence?: {
    evidence_units?: Array<{
      ref: string;
      kind: string;
      label: string;
      value?: unknown;
      object_ref?: string | null;
    }>;
  };
}

const TECHNICAL_LABELS = new Set([
  "sku",
  "has active listing",
  "listing count",
  "item status",
  "status",
]);

/**
 * Decisive evidence cards for the Librarian. Prefers bundle metrics, falls
 * back to cited evidence units; drops technical labels and booleans.
 */
export function decisiveCards(
  answer: MinimalAnswer | null,
  bundle: MinimalBundle | null,
): EvidenceCard[] {
  if (!bundle) return [];
  const cards: EvidenceCard[] = [];
  const seen = new Set<string>();
  const listing = bundle.objects?.find((o) => o.type === "Listing");
  const item = bundle.objects?.find((o) => o.type === "Item");
  const source = listing
    ? `${channelName(listing.properties?.platform)} listing`
    : item
      ? `${productLabel(item)}`
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
    const label = humanLabel(key);
    if (seen.has(label.toLowerCase())) continue;
    seen.add(label.toLowerCase());
    cards.push({ label, value: formatted, source, observed });
    if (cards.length >= 6) return cards;
  }
  if (cards.length >= 4) return cards;

  const units = [
    ...(answer?.evidence?.evidence_units || []),
  ];
  const byRef = new Map(units.map((unit) => [unit.ref, unit]));
  const cited = (answer?.evidence_refs || [])
    .map((ref) => byRef.get(ref) || { ref, kind: "unknown", label: ref, value: null })
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
    const label = humanLabel(unit.label);
    if (seen.has(label.toLowerCase())) continue;
    seen.add(label.toLowerCase());
    cards.push({
      label,
      value: formatted,
      source:
        caption(bundle, unit.object_ref) ||
        source,
      observed,
      ref: unit.ref,
    });
    if (cards.length >= 6) break;
  }
  return cards;
}

function caption(bundle: MinimalBundle, objectRef?: string | null): string | null {
  if (!objectRef) return null;
  const [type, id] = objectRef.split(":");
  const obj = bundle.objects?.find((o) => o.type === type && String(o.id) === id);
  if (obj) return productLabel(obj);
  if (type === "Item") return id;
  return humanLabel(type);
}

function productLabel(obj: { type: string; id: string; properties?: Record<string, unknown> }): string {
  if (obj.type === "Item") return String(obj.properties?.product || obj.id);
  if (obj.type === "Listing") return `${channelName(obj.properties?.platform)} listing`;
  if (obj.type === "Channel") return channelName(obj.properties?.platform || obj.id);
  return humanLabel(obj.type);
}

export function channelName(value: unknown): string {
  const s = String(value || "").trim();
  if (!s) return "—";
  return s.charAt(0).toUpperCase() + s.slice(1);
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

export function attentionTone(reason?: string | null): "bad" | "warn" | "info" {
  if (reason === "unlisted_owned") return "info";
  if (reason === "listed_active") return "info";
  return "warn";
}

export interface AttentionRowLike {
  sku: string;
  product?: string;
  item_status?: string;
  attention_reason?: string;
  listing_age_days?: number | null;
  inventory_age_days?: number | null;
  watchers?: number | null;
  offers?: number | null;
  views?: number | null;
  watch_rate?: number | null;
}

export function attentionMeta(row: AttentionRowLike): string {
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

export function rankAttention<T extends AttentionRowLike>(queue: T[]): T[] {
  const review: T[] = [];
  const monitor: T[] = [];
  const unlisted: T[] = [];
  for (const row of queue) {
    if (row.attention_reason === "unlisted_owned") unlisted.push(row);
    else if (row.attention_reason === "listed_active") monitor.push(row);
    else review.push(row);
  }
  const shown: T[] = [];
  shown.push(...review.slice(0, 6));
  shown.push(...monitor.slice(0, 2));
  const remaining = Math.max(4, 12 - shown.length);
  shown.push(...unlisted.slice(0, remaining));
  return shown;
}

export function parseRef(ref: string): { type: string; id: string } {
  const idx = ref.indexOf(":");
  if (idx === -1) return { type: ref, id: "" };
  return { type: ref.slice(0, idx), id: ref.slice(idx + 1) };
}

export function eventLabel(type: unknown): string {
  const raw = String(type || "event");
  if (/price.?change/i.test(raw)) return "Price change";
  if (/listing.?opened/i.test(raw)) return "Listing opened";
  return humanLabel(raw);
}

export function whyText(why: string): string {
  if (!why) return "";
  return why.replace(/[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+/g, (token) =>
    humanLabel(token).toLowerCase(),
  );
}

export function collapseTimeline<T extends { type?: unknown; at?: unknown }>(
  events: T[],
): T[] {
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

export function typeLabel(type: string): string {
  if (type === "EngagementObservation") return "Engagement";
  if (type === "BusinessSnapshot") return "Snapshot";
  return type;
}
