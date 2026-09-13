import type { AttentionQueue, BusinessSnapshot } from "./types";
import { Field, Section } from "./ui";

export function OverviewPage({
  snapshot,
  attention,
  onOpenSku,
}: {
  snapshot: BusinessSnapshot | null;
  attention: AttentionQueue | null;
  onOpenSku: (sku: string) => void;
}) {
  const data = snapshot?.data || {};
  const recs = attention?.data?.recommendations || [];
  const queue = attention?.data?.queue || [];
  const asOf = String(snapshot?.provenance?.as_of || "");
  const productFor = (sku: string) =>
    queue.find((row) => row.sku === sku)?.product || sku;
  return (
    <div data-testid="overview-page" className="overview-layout">
      <Section title="Needs attention">
        {recs.length ? (
          recs.slice(0, 12).map((r) => (
            <div
              key={r.sku}
              className="row"
              data-testid={`attention-${r.sku}`}
              onClick={() => onOpenSku(r.sku)}
            >
              <span>
                <strong>{productFor(r.sku)}</strong>
                <span className="dim"> {r.sku}</span>
              </span>
              <span className="lede" style={{ margin: 0 }}>{r.why || r.action || r.attention_reason}</span>
            </div>
          ))
        ) : (
          <p className="lede">No attention items.</p>
        )}
      </Section>
      <div className="overview-side">
        <Section title="Inventory state">
          <div data-testid="overview-items-total">
            <Field label="items" value={data.items_total} />
          </div>
          <Field label="owned unlisted" value={data.owned_unlisted} />
          <Field label="listed" value={data.listed_items} />
          <Field label="sold" value={data.sold_items} />
        </Section>
        <Section title="Capital exposure">
          <Field label="capital tied up CNY" value={data.capital_tied_up_cny} />
          <Field label="USD estimate (display FX)" value={data.capital_tied_up_usd_est} />
          <p className="lede">Fee-adjusted revenue is not margin.</p>
        </Section>
        <Section title="Freshness">
          <Field label="stale active listings" value={data.stale_active_listings} />
          <Field label="as of" value={asOf || "—"} />
        </Section>
      </div>
    </div>
  );
}
