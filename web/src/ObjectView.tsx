import { useState } from "react";
import { ActionPanel } from "./ActionPanel";
import {
  attentionAction,
  collapseTimeline,
  eventLabel,
  formatChannel,
  formatDays,
  formatMoney,
  observedDate,
  productName,
} from "./format";
import { Field, StatusChip } from "./ui";
import type { AttentionQueueRow, ItemHistory, ItemPayload } from "./types";

type ObjectTab =
  | "listings"
  | "engagement"
  | "orders"
  | "history"
  | "notes"
  | "related"
  | "provenance";

export function ObjectView({
  item,
  history,
  attention,
  compact,
  onBack,
  onAskLibrarian,
  onReload,
}: {
  item: ItemPayload;
  history: ItemHistory | null;
  attention?: AttentionQueueRow | null;
  compact?: boolean;
  onBack?: () => void;
  onAskLibrarian: (sku: string) => void;
  onReload: () => void;
}) {
  const itemData = item.data?.item ?? {};
  const listings = item.data?.listings ?? [];
  const orders = item.data?.orders ?? [];
  const timeline = collapseTimeline(history?.data?.timeline ?? []);
  const engagement = history?.data?.engagement ?? [];
  const sku = String(itemData.sku || "");
  const active = listings.find((l) => l.status === "active") || listings[0];
  const [tab, setTab] = useState<ObjectTab>("listings");
  const visibleHistory = compact || tab !== "history" ? timeline.slice(-4) : timeline;
  const name = productName(itemData);
  const listingState = active
    ? `${formatChannel(active.platform)} · ${active.status || "—"}`
    : "not listed";
  const noteText = itemData.notes ? String(itemData.notes) : "";

  return (
    <div data-testid="item-view" className={compact ? "object-pane compact" : "object-pane"}>
      {onBack && (
        <button type="button" className="back" onClick={onBack}>
          ← Inventory
        </button>
      )}
      <div className="object-header">
        <div>
          <div className="kicker">Item</div>
          <div className="object-title-row">
            <h2 className="object-name">{name}</h2>
            <StatusChip tone={String(itemData.status) === "listed" ? "warn" : "muted"}>
              {String(itemData.status || "—")}
            </StatusChip>
            {attention?.attention_reason ? (
              <StatusChip tone="warn">{attentionAction(attention.attention_reason)}</StatusChip>
            ) : null}
          </div>
        </div>
        {sku && !compact ? (
          <div className="object-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => onAskLibrarian(sku)}
            >
              Ask Librarian
            </button>
          </div>
        ) : null}
      </div>

      <dl className="props" data-testid="item-state">
        <div className="prop">
          <dt>Lifecycle</dt>
          <dd>{String(itemData.status || "—")}</dd>
        </div>
        <div className="prop">
          <dt>Acquisition</dt>
          <dd>{formatMoney(itemData.acquisition_cost_cny, "CNY")}</dd>
        </div>
        <div className="prop">
          <dt>Listing</dt>
          <dd>{listingState}</dd>
        </div>
        <div className="prop">
          <dt>Price</dt>
          <dd>{formatMoney(active?.price_usd ?? itemData.target_price_usd, "USD")}</dd>
        </div>
        <div className="prop">
          <dt>Age</dt>
          <dd>
            {active?.listing_age_days != null
              ? formatDays(active.listing_age_days, "days listed")
              : formatDays(itemData.inventory_age_days, "days in inventory")}
          </dd>
        </div>
        <div className="prop">
          <dt>Attention</dt>
          <dd>{attention ? attentionAction(attention.attention_reason) : "—"}</dd>
        </div>
      </dl>

      {!compact && (
        <div className="tabs-inline">
          {(
            [
              ["listings", "Listings"],
              ["engagement", "Engagement"],
              ["orders", "Orders"],
              ["history", "History"],
              ["notes", "Notes"],
              ["related", "Related"],
              ["provenance", "Provenance"],
            ] as Array<[ObjectTab, string]>
          ).map(([id, label]) => (
            <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
              {label}
            </button>
          ))}
        </div>
      )}

      {!compact && tab === "listings" && (
        <section className="card" style={{ marginBottom: 12 }}>
          <h2>Listings</h2>
          {listings.length ? (
            listings.map((l, i) => (
              <div key={String(l.listing_id || i)} className="listing-block">
                <Field label="Channel" value={formatChannel(l.platform)} />
                <Field label="State" value={l.status} />
                <Field label="Price" value={formatMoney(l.price_usd, "USD")} />
                <Field label="Age" value={formatDays(l.listing_age_days)} />
                <Field label="Watchers" value={l.watchers} />
                <Field label="Offers" value={l.offers} />
              </div>
            ))
          ) : (
            <p className="empty">No listings.</p>
          )}
        </section>
      )}

      {!compact && tab === "engagement" && (
        <section className="card">
          <h2>Engagement</h2>
          {listings.some((l) => l.watchers || l.offers || l.views) ? (
            listings.map((l, i) => (
              <div key={String(l.listing_id || i)} className="listing-block">
                <Field label="Channel" value={formatChannel(l.platform)} />
                <Field label="Views" value={l.views} />
                <Field label="Watchers" value={l.watchers} />
                <Field label="Offers" value={l.offers} />
                <Field
                  label="Watch rate"
                  value={typeof l.watch_rate === "number" ? `${(l.watch_rate * 100).toFixed(1)}%` : "—"}
                />
              </div>
            ))
          ) : engagement.length ? (
            engagement.slice(0, 12).map((e, i) => (
              <p key={i} className="hist">
                <span className="dim">{observedDate(String(e.snapshot_at || "")) || "—"}</span>{" "}
                {String(e.watchers ?? 0)} watchers · {String(e.offers ?? 0)} offers
              </p>
            ))
          ) : (
            <p className="empty">No engagement snapshots.</p>
          )}
        </section>
      )}

      {!compact && tab === "orders" && (
        <section className="card">
          <h2>Orders</h2>
          {orders.length ? (
            orders.map((o, i) => (
              <div key={i}>
                <Field label="Sale" value={formatMoney(o.price_usd, "USD")} />
                <Field label="Status" value={o.status} />
              </div>
            ))
          ) : (
            <p className="empty">No orders.</p>
          )}
        </section>
      )}

      {!compact && (tab === "listings" || tab === "history") && (
        <section className="card" data-testid="item-timeline" style={{ marginBottom: 12 }}>
          <h2>{tab === "history" && !compact ? "History" : "Recent history"}</h2>
          {visibleHistory.length ? (
            visibleHistory.map((e, i) => (
              <p key={i} className="hist">
                <span className="dim">{observedDate(String(e.at || "")) || "—"}</span> {eventLabel(e.type)}
              </p>
            ))
          ) : (
            <p className="empty">No history.</p>
          )}
        </section>
      )}

      {!compact && tab === "notes" && (
        <section className="card">
          <h2>Notes</h2>
          {noteText ? <p>{noteText}</p> : <p className="empty">No notes on this object.</p>}
        </section>
      )}

      {!compact && tab === "related" && (
        <section className="card">
          <h2>Related objects</h2>
          {listings.map((l, i) => (
            <p key={i} className="hist">
              {formatChannel(l.platform)} listing · {String(l.status || "")}
            </p>
          ))}
          {orders.map((o, i) => (
            <p key={`o${i}`} className="hist">
              Order {o.status ? String(o.status) : ""}
            </p>
          ))}
          {!listings.length && !orders.length ? <p className="empty">No linked objects.</p> : null}
        </section>
      )}

      {!compact && tab === "provenance" && (
        <section className="card">
          <h2>Provenance</h2>
          <Field label="tool" value={item.provenance?.tool} />
          <Field label="as of" value={observedDate(String(item.provenance?.as_of || "")) || item.provenance?.as_of} />
        </section>
      )}

      {sku ? <ActionPanel sku={sku} onApplied={onReload} /> : null}
    </div>
  );
}
