import type { ReactNode } from "react";
import type { ContextObject } from "./types";

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

export function Section({
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

export function Field({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="field">
      <dt>{label}</dt>
      <dd className="mono">{kv(value)}</dd>
    </div>
  );
}

export function objectLabel(objects: ContextObject[], ref: string): string {
  const idx = ref.indexOf(":");
  const type = idx === -1 ? ref : ref.slice(0, idx);
  const id = idx === -1 ? "" : ref.slice(idx + 1);
  const obj = objects.find((o) => o.type === type && String(o.id) === id);
  const props = obj?.properties || {};
  if (type === "Item") return String(props.product || id || ref);
  if (type === "Listing") {
    const platform = props.platform ? String(props.platform) : "listing";
    return `${platform.charAt(0).toUpperCase()}${platform.slice(1)} listing`;
  }
  if (type === "Channel") {
    const platform = String(props.platform || id);
    return platform.charAt(0).toUpperCase() + platform.slice(1);
  }
  if (type === "Order") return `order ${id}`;
  if (type === "Recommendation") return `recommendation for ${props.sku || id}`;
  if (type === "EngagementObservation") return "engagement";
  if (type === "IngestRun") return "ingest trust";
  return obj ? `${type} ${id}` : ref;
}

export function relVerb(type: string): string {
  const map: Record<string, string> = {
    HAS_LISTING: "listed as",
    ON_CHANNEL: "on",
    HAS_ENGAGEMENT: "has",
    RESULTED_IN: "sold as",
    TARGETS: "targets",
  };
  return map[type] || type.toLowerCase().replace(/_/g, " ");
}

export function itemLabel(obj: ContextObject): string {
  if (obj.type === "Item") return String(obj.properties?.product || obj.id);
  if (obj.type === "Listing") return `${obj.properties?.platform || "listing"} listing`;
  if (obj.type === "Channel") return String(obj.properties?.platform || obj.id);
  if (obj.type === "Order") return `order ${obj.id}`;
  if (obj.type === "Recommendation") return `rec · ${obj.properties?.sku || obj.id}`;
  if (obj.type === "EngagementObservation") return "engagement";
  if (obj.type === "IngestRun") return "ingest trust";
  return `${obj.type} ${obj.id}`;
}

export function parseRef(ref: string): { type: string; id: string } {
  const idx = ref.indexOf(":");
  if (idx === -1) return { type: ref, id: "" };
  return { type: ref.slice(0, idx), id: ref.slice(idx + 1) };
}
