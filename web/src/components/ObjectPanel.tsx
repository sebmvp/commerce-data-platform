import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { ArrowLeft, Sparkles, X } from "lucide-react";
import { ErrorNote, LoadingDots } from "@/App";
import { Field, Section, StatusChip } from "@/components/primitives";
import { ActionPanel } from "@/components/ActionPanel";
import { ContextualLibrarian } from "@/components/ContextualLibrarian";
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
import { useItem, useItemHistory, useAttention } from "@/lib/api";
import type { AttentionQueueRow, ItemHistory, ItemPayload } from "@/types";

/**
 * Object workspace panel — identity, state strip, related sections, sandbox
 * action; provenance behind disclosure. Mounted from Inventory (`?sku=`,
 * table stays mounted) and from the /inventory/$sku deep link.
 */
export function ObjectPanel({ sku, status }: { sku: string; status?: string }) {
  const item = useItem(sku);
  const history = useItemHistory(sku);
  const attention = useAttention();
  const navigate = useNavigate();
  const search = (useSearch({ strict: false }) || {}) as Record<string, unknown>;
  const askOpen = String(search.ask || "") === "1";
  const attentionRow =
    attention.data?.data?.queue?.find((r) => r.sku === sku) || null;

  function closePanel() {
    void navigate({ to: "/inventory", search: status ? { status } : {} });
  }

  return (
    <div className="flex h-full flex-col" data-testid="item-view">
      <div
        className="flex items-center justify-between gap-2 border-b px-4 py-2.5"
        style={{ borderColor: "var(--border-subtle)" }}
      >
        <button
          type="button"
          data-testid="back-to-inventory"
          onClick={closePanel}
          className="inline-flex items-center gap-1 text-[12.5px] focus-ring"
          style={{ color: "var(--text-muted)" }}
        >
          <ArrowLeft size={13} /> Inventory
        </button>
        <button
          type="button"
          aria-label="Close panel"
          data-testid="close-panel"
          onClick={closePanel}
          className="rounded p-1 focus-ring"
          style={{ color: "var(--text-muted)" }}
        >
          <X size={14} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {item.isError ? (
          <ErrorNote error={item.error} retry={() => void item.refetch()} />
        ) : item.isPending || !item.data ? (
          <div className="pt-2">
            <LoadingDots label="Loading item…" />
          </div>
        ) : (
          <PanelBody
            sku={sku}
            item={item.data}
            refetch={item.refetch}
            history={history.data}
            historyPending={history.isPending}
            attentionRow={attentionRow}
            askOpen={askOpen}
          />
        )}
      </div>
    </div>
  );
}

function PanelBody({
  sku,
  item,
  refetch,
  history,
  historyPending,
  attentionRow,
  askOpen,
}: {
  sku: string;
  item: ItemPayload;
  refetch: () => Promise<unknown>;
  history?: ItemHistory;
  historyPending: boolean;
  attentionRow: AttentionQueueRow | null;
  askOpen: boolean;
}) {
  const itemData = item.data?.item ?? {};
  const listings = item.data?.listings ?? [];
  const orders = item.data?.orders ?? [];
  const timeline = collapseTimeline(history?.data?.timeline ?? []);
  const engagement = history?.data?.engagement ?? [];
  const active = listings.find((l) => l.status === "active") || listings[0];
  const isListed = String(itemData.status) === "listed";
  const listingState = active
    ? `${channelName(active.platform)} · ${active.status || "—"}`
    : "not listed";
  const noteText = itemData.notes ? String(itemData.notes) : "";

  return (
    <div data-testid="panel-body">
      <div className="min-w-0">
        <div className="text-[11px] uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
          Item
        </div>
        <div className="mt-1 flex flex-wrap items-baseline gap-2">
          <h2
            className="text-[20px] font-semibold tracking-tight"
            style={{ color: "var(--text-primary)" }}
          >
            {productName(itemData, sku)}
          </h2>
          <StatusChip tone={isListed ? "warn" : "muted"}>
            {String(itemData.status || "—")}
          </StatusChip>
          {attentionRow?.attention_reason ? (
            <StatusChip tone="warn">
              {attentionAction(attentionRow.attention_reason)}
            </StatusChip>
          ) : null}
        </div>
        <div className="tabular mt-0.5 text-[12.5px]" style={{ color: "var(--text-muted)" }}>
          {attentionRow ? attentionMeta(attentionRow) : ""}
        </div>
        {!askOpen ? (
          <Link
            to="/inventory/$sku"
            params={{ sku }}
            search={{ ask: 1 }}
            className="mt-3 flex items-center justify-center gap-1.5 rounded border px-3 py-2 text-[13.5px] font-medium focus-ring"
            style={{
              borderColor: "var(--accent-primary)",
              color: "var(--accent-faint)",
              background: "var(--surface-1)",
            }}
            data-testid="ask-librarian"
          >
            <Sparkles size={14} /> Ask Librarian
          </Link>
        ) : null}
      </div>

      {askOpen ? (
        <div className="mt-3" data-testid="contextual-librarian">
          <ContextualLibrarian
            sku={sku}
            attentionReason={(attentionRow?.attention_reason as string) || null}
          />
        </div>
      ) : null}

      <dl
        className="mt-4 grid grid-cols-3 gap-x-4 gap-y-3 rounded border px-3.5 py-3"
        style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}
        data-testid="item-state"
      >
        <Prop label="Lifecycle" value={String(itemData.status || "—")} />
        <Prop label="Acquisition" value={formatMoney(itemData.acquisition_cost_cny, "CNY")} />
        <Prop label="Listing" value={listingState} />
        <Prop
          label="Price"
          value={formatMoney(active?.price_usd ?? itemData.target_price_usd, "USD")}
        />
        <Prop
          label="Age"
          value={
            active?.listing_age_days != null
              ? formatDays(active.listing_age_days, "days listed")
              : formatDays(itemData.inventory_age_days as number | undefined, "days in inventory")
          }
        />
        <Prop
          label="Attention"
          value={attentionRow ? attentionAction(attentionRow.attention_reason) : "—"}
        />
      </dl>

      <div className="mt-5">
        <Section title="Listings" testId="item-listings">
          {listings.length ? (
            listings.map((l) => (
              <div
                key={String(l.listing_id || l.platform || "listing")}
                className="border-b py-2 last:border-0" style={{ borderColor: "var(--border-subtle)" }}>
                <div className="flex items-baseline justify-between gap-2 pb-1">
                  <span className="text-[13.5px] font-medium" style={{ color: "var(--text-primary)" }}>
                    {channelName(l.platform)} · {String(l.status || "—")}
                  </span>
                  <span className="tabular text-[13.5px]" style={{ color: "var(--text-primary)" }}>
                    {formatMoney(l.price_usd, "USD")}
                  </span>
                </div>
                <div className="tabular grid grid-cols-3 gap-x-3 text-[12px]">
                  <span style={{ color: "var(--text-muted)" }}>{l.listing_age_days != null ? `${l.listing_age_days}d` : "—"}</span>
                  <span style={{ color: "var(--text-muted)" }}>{l.watchers ?? 0} watchers</span>
                  <span style={{ color: "var(--text-muted)" }}>{l.offers ?? 0} offers</span>
                </div>
              </div>
            ))
          ) : (
            <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
              Not listed on any channel.
            </p>
          )}
        </Section>

        <Section title="Engagement" testId="item-engagement">
          {historyPending ? (
            <LoadingDots label="Loading engagement…" />
          ) : engagement.length ? (
            engagement.slice(0, 8).map((e, i) => (
              <div
                key={i}
                className="flex items-baseline justify-between gap-3 border-b py-1.5 last:border-0"
                style={{ borderColor: "var(--border-subtle)" }}
              >
                <span className="tabular text-[12.5px]" style={{ color: "var(--text-muted)" }}>
                  {observedDate(String((e as Record<string, unknown>).snapshot_at || "")) || "—"}
                </span>
                <span className="tabular text-[12.5px]" style={{ color: "var(--text-secondary)" }}>
                  {String((e as Record<string, unknown>).watchers ?? 0)} watchers ·{" "}
                  {String((e as Record<string, unknown>).offers ?? 0)} offers
                </span>
              </div>
            ))
          ) : listings.some((l) => l.views || l.watchers) ? (
            listings.map((l, i) => (
              <div key={String(l.listing_id || i)} className="py-1">
                <Field
                  label={channelName(l.platform)}
                  value={`views ${l.views ?? "—"} · watchers ${l.watchers ?? "—"}`}
                />
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
              <div
                key={i}
                className="flex items-baseline justify-between gap-2 border-b py-1.5 last:border-0"
                style={{ borderColor: "var(--border-subtle)" }}
              >
                <span className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
                  {String(o.status || "Sale")}
                </span>
                <span className="tabular text-[13px]" style={{ color: "var(--text-primary)" }}>
                  {formatMoney(o.price_usd, "USD")}
                </span>
              </div>
            ))
          ) : (
            <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
              No orders.
            </p>
          )}
        </Section>

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

        <details className="mt-5" data-testid="item-provenance">
          <summary className="cursor-pointer text-[12.5px] focus-ring" style={{ color: "var(--text-muted)" }}>
            Provenance
          </summary>
          <div className="mt-2">
            <Field label="tool" value={(item.provenance?.tool as string) || "—"} />
            <Field
              label="as of"
              value={
                observedDate(String(item.provenance?.as_of || "")) ||
                String(item.provenance?.as_of || "—")
              }
            />
          </div>
        </details>

        <div className="mt-5">
          <ActionPanel sku={sku} onChanged={() => void refetch()} />
        </div>
      </div>
    </div>
  );
}

function Prop({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="section-label">{label}</dt>
      <dd
        className="tabular mt-0.5 text-[13.5px] font-medium"
        style={{ color: "var(--text-primary)" }}
      >
        {value}
      </dd>
    </div>
  );
}
