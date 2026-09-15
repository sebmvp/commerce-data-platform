import { Link, useParams } from "@tanstack/react-router";
import { ArrowLeft, Sparkles } from "lucide-react";
import { ErrorNote, LoadingDots } from "@/App";
import { Field, Section, StatusChip } from "@/components/primitives";
import { ActionPanel } from "@/components/ActionPanel";
import {
  attentionAction,
  attentionMeta,
  channelName,
  collapseTimeline,
  eventLabel,
  formatDays,
  formatMoney,
  observedDate,
  productName,
} from "@/lib/format";
import { useAttention, useItem, useItemHistory } from "@/lib/api";

export function ItemDetailPage() {
  const { sku } = useParams({ strict: false }) as { sku: string };
  const item = useItem(sku);
  const history = useItemHistory(sku);
  const attention = useAttention();
  const attentionRow = attention.data?.data?.queue?.find((r) => r.sku === sku) || null;

  if (item.isError) {
    return (
      <div className="mx-auto max-w-6xl px-5 py-6">
        <BackToInventory sku={sku} />
        <ErrorNote error={item.error} retry={() => void item.refetch()} />
      </div>
    );
  }
  if (item.isPending || !item.data) {
    return (
      <div className="mx-auto max-w-6xl px-5 py-4">
        <BackToInventory sku={sku} />
        <div className="mt-4">
          <LoadingDots label="Loading item…" />
        </div>
      </div>
    );
  }

  const itemData = item.data.data?.item ?? {};
  const listings = item.data.data?.listings ?? [];
  const orders = item.data.data?.orders ?? [];
  const timeline = collapseTimeline(history.data?.data?.timeline ?? []);
  const engagement = history.data?.data?.engagement ?? [];
  const active = listings.find((l) => l.status === "active") || listings[0];
  const isListed = String(itemData.status) === "listed";
  const listingState = active
    ? `${channelName(active.platform)} · ${active.status || "—"}`
    : "not listed";
  const noteText = itemData.notes ? String(itemData.notes) : "";

  return (
    <div className="mx-auto max-w-6xl px-5 py-4" data-testid="item-view">
      <BackToInventory sku={sku} />

      <div className="mt-2 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="kicker text-[11px] uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
            Item
          </div>
          <div className="flex flex-wrap items-baseline gap-2">
            <h1 className="text-[20px] font-semibold tracking-tight" style={{ color: "var(--text-primary)" }}>
              {productName(itemData, sku)}
            </h1>
            <StatusChip tone={isListed ? "warn" : "muted"}>{String(itemData.status || "—")}</StatusChip>
            {attentionRow?.attention_reason ? (
              <StatusChip tone="warn">{attentionAction(attentionRow.attention_reason)}</StatusChip>
            ) : null}
          </div>
          <div className="mt-0.5 text-[12.5px]" style={{ color: "var(--text-muted)" }}>
            {sku} {attentionRow ? `· ${attentionMeta(attentionRow)}` : ""}
          </div>
        </div>
        <Link
          to="/librarian/$sku"
          params={{ sku }}
          className="btn-primary flex items-center gap-1.5 rounded border px-3 py-1.5 text-[13.5px] font-medium focus-ring"
          style={{ borderColor: "var(--accent-primary)", color: "var(--accent-faint)", background: "var(--surface-1)" }}
          data-testid="ask-librarian"
        >
          <Sparkles size={14} /> Ask Librarian
        </Link>
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-x-6 gap-y-3 rounded border px-4 py-3 max-[820px]:grid-cols-2" style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }} data-testid="item-state">
        <Prop label="Lifecycle" value={String(itemData.status || "—")} />
        <Prop label="Acquisition" value={formatMoney(itemData.acquisition_cost_cny, "CNY")} />
        <Prop label="Listing" value={listingState} />
        <Prop label="Price" value={formatMoney(active?.price_usd ?? itemData.target_price_usd, "USD")} />
        <Prop
          label="Age"
          value={
            active?.listing_age_days != null
              ? formatDays(active.listing_age_days, "days listed")
              : formatDays(itemData.inventory_age_days, "days in inventory")
          }
        />
        <Prop label="Attention" value={attentionRow ? attentionAction(attentionRow.attention_reason) : "—"} />
      </dl>

      <div className="mt-5 grid grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] gap-6 max-[1100px]:grid-cols-1">
        <div className="space-y-5">
          <Section title="Listings" testId="item-listings">
            {listings.length ? (
              listings.map((l, i) => (
                <div
                  key={String(l.listing_id || i)}
                  className="border-b py-2 last:border-0"
                  style={{ borderColor: "var(--border-subtle)" }}
                >
                  <div className="grid grid-cols-3 gap-x-4">
                    <Field label="Channel" value={channelName(l.platform)} />
                    <Field label="State" value={l.status} />
                    <Field label="Price" value={formatMoney(l.price_usd, "USD")} />
                    <Field label="Age" value={formatDays(l.listing_age_days)} />
                    <Field label="Watchers" value={l.watchers} />
                    <Field label="Offers" value={l.offers} />
                  </div>
                </div>
              ))
            ) : (
              <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                Not listed on any channel.
              </p>
            )}
          </Section>

          <Section title="Engagement">
            {listings.some((l) => l.watchers || l.offers || l.views) ? (
              listings.map((l, i) => (
                <div key={String(l.listing_id || i)} className="py-1.5">
                  <Field label="Channel" value={channelName(l.platform)} />
                  <Field label="Views" value={l.views} />
                  <Field label="Watch rate" value={typeof l.watch_rate === "number" ? `${(l.watch_rate * 100).toFixed(1)}%` : "—"} />
                </div>
              ))
            ) : engagement.length ? (
              engagement.slice(0, 10).map((e, i) => (
                <div key={i} className="py-0.5 text-[13px]">
                  <span className="tabular" style={{ color: "var(--text-muted)" }}>
                    {observedDate(String(e.snapshot_at || "")) || "—"}
                  </span>{" "}
                  {String(e.watchers ?? 0)} watchers · {String(e.offers ?? 0)} offers
                </div>
              ))
            ) : (
              <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                No engagement snapshots.
              </p>
            )}
          </Section>

          <Section title="Orders">
            {orders.length ? (
              orders.map((o, i) => (
                <div key={i} className="py-0.5">
                  <Field label="Sale" value={formatMoney(o.price_usd, "USD")} />
                  <Field label="Status" value={String(o.status || "")} />
                </div>
              ))
            ) : (
              <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                No orders.
              </p>
            )}
          </Section>
        </div>

        <div className="space-y-5">
          <Section title="History" testId="item-timeline">
            {timeline.length ? (
              timeline.map((e, i) => (
                <div key={i} className="flex items-baseline gap-2 py-1 text-[13px]">
                  <span className="tabular w-16 shrink-0" style={{ color: "var(--text-muted)" }}>
                    {observedDate(String(e.at || "")) || "—"}
                  </span>
                  <span style={{ color: "var(--text-secondary)" }}>{eventLabel(e.type)}</span>
                </div>
              ))
            ) : (
              <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                No history.
              </p>
            )}
          </Section>

          <Section title="Notes" testId="item-notes">
            {noteText ? (
              <p className="text-[13.5px]" style={{ color: "var(--text-secondary)" }}>
                {noteText}
              </p>
            ) : (
              <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                No notes on this object.
              </p>
            )}
          </Section>

          <Section title="Provenance">
            <Field label="tool" value={item.data?.provenance?.tool as string} />
            <Field
              label="as of"
              value={observedDate(String(item.data?.provenance?.as_of || "")) || String(item.data?.provenance?.as_of || "—")}
            />
          </Section>

          <ActionPanel sku={sku} onChanged={() => void item.refetch()} />
        </div>
      </div>
    </div>
  );
}

function Prop({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="section-label">{label}</dt>
      <dd className="mt-0.5 text-[14px] font-medium" style={{ color: "var(--text-primary)" }}>
        {value}
      </dd>
    </div>
  );
}

function BackToInventory({ sku }: { sku: string }) {
  void sku;
  return (
    <Link
      to="/inventory"
      data-testid="back-to-inventory"
      className="inline-flex items-center gap-1 text-[13px] focus-ring"
      style={{ color: "var(--text-muted)" }}
    >
      <ArrowLeft size={13} /> Inventory
    </Link>
  );
}
