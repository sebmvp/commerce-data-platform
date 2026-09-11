import { useMemo, useState } from "react";
import { ActionPanel } from "./ActionPanel";
import type { InventoryRow } from "./types";
import { Field, Section } from "./ui";

export function InventoryPage({
  sku,
  setSku,
  inventory,
  invFilter,
  setFilter,
  item,
  history,
  onLoad,
  onReloadItem,
  onAskItem,
}: {
  sku: string;
  setSku: (v: string) => void;
  inventory: InventoryRow[];
  invFilter: string;
  setFilter: (v: string) => void;
  item: any;
  history: any;
  onLoad: (sku: string) => void;
  onReloadItem: () => void;
  onAskItem: (sku: string) => void;
}) {
  const itemData = item?.data?.item ?? item?.data ?? {};
  const listings = item?.data?.listings ?? [];
  const orders = item?.data?.orders ?? [];
  const timeline = history?.data?.timeline ?? [];
  const [search, setSearch] = useState("");
  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return inventory;
    return inventory.filter((row) =>
      `${row.product || ""} ${row.sku} ${row.status}`.toLowerCase().includes(q)
    );
  }, [inventory, search]);

  return (
    <>
      <form
        className="ask"
        onSubmit={(e) => {
          e.preventDefault();
          onLoad(sku);
        }}
      >
        <input data-testid="sku-input" value={sku} onChange={(e) => setSku(e.target.value)} placeholder="sku" />
        <button type="submit">Load</button>
      </form>
      <form className="ask" onSubmit={(e) => e.preventDefault()}>
        <input
          data-testid="inventory-search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="search product or sku"
        />
      </form>
      <div className="samples">
        {[
          { id: "", label: "all" },
          { id: "owned", label: "owned" },
          { id: "listed", label: "listed" },
          { id: "sold", label: "sold" },
        ].map((st) => (
          <button
            key={st.label}
            className={`chip ${invFilter === st.id ? "active" : ""}`}
            onClick={() => setFilter(st.id)}
          >
            {st.label}
          </button>
        ))}
      </div>
      {visible.length > 0 && (
        <Section title="Items">
          {visible.map((row) => (
            <div key={row.sku} className="row" onClick={() => onLoad(row.sku)}>
              <span>
                <strong>{row.product || row.sku}</strong>
                <span className="dim"> {row.sku}</span>
              </span>
              <span className="lede" style={{ margin: 0 }}>{row.status}</span>
            </div>
          ))}
        </Section>
      )}
      {item && (
        <div className="grid" data-testid="item-view">
          <Section title="Identity / current state" testId="item-state">
            <h2 className="object-name">{itemData.product || itemData.sku}</h2>
            <p className="lede">{itemData.status} · {itemData.sku}</p>
            <Field label="acquisition CNY" value={itemData.acquisition_cost_cny} />
            <Field label="target usd" value={itemData.target_price_usd} />
            <Field label="inventory age" value={itemData.inventory_age_days} />
          </Section>
          <Section title="Listings">
            {listings.length ? listings.map((l: any, i: number) => (
              <div key={i} className="listing-block">
                <Field label="platform" value={l.platform} />
                <Field label="status" value={l.status} />
                <Field label="price usd" value={l.price_usd} />
                <Field label="age days" value={l.listing_age_days} />
                <Field label="watchers" value={l.watchers} />
                <Field label="offers" value={l.offers} />
              </div>
            )) : <p className="lede">No listings.</p>}
          </Section>
          <Section title="Orders">
            {orders.length ? orders.map((o: any, i: number) => (
              <div key={i}>
                <Field label="order" value={o.order_id} />
                <Field label="sale usd" value={o.price_usd} />
              </div>
            )) : <p className="lede">No orders.</p>}
          </Section>
          <Section title="Timeline / history" testId="item-timeline">
            <pre className="mono">
              {timeline.map((e: any) => `${e.at ?? "?"}  ${e.type}`).join("\n") || "—"}
            </pre>
          </Section>
          {itemData.sku && (
            <>
              <button
                className="chip"
                onClick={() => onAskItem(itemData.sku)}
              >
                Ask about this item
              </button>
              <ActionPanel sku={itemData.sku} onApplied={onReloadItem} />
            </>
          )}
        </div>
      )}
    </>
  );
}
