import { Field, Section } from "./ui";

export function OverviewPage({
  snapshot,
  attention,
  onOpenSku,
}: {
  snapshot: any;
  attention: any;
  onOpenSku: (sku: string) => void;
}) {
  const data = snapshot?.data || {};
  const recs = attention?.data?.recommendations || [];
  return (
    <div data-testid="overview-page">
      <div className="grid">
        <Section title="Inventory state">
          <Field label="items" value={data.items_total} />
          <Field label="owned unlisted" value={data.owned_unlisted} />
          <Field label="listed" value={data.listed_items} />
          <Field label="sold" value={data.sold_items} />
          <Field label="active listings" value={data.active_listings} />
        </Section>
        <Section title="Capital and sales">
          <Field label="capital tied up CNY" value={data.capital_tied_up_cny} />
          <Field label="USD estimate (display FX)" value={data.capital_tied_up_usd_est} />
          <Field label="realized revenue USD" value={data.realized_revenue_usd} />
          <Field label="gross after fees USD" value={data.realized_gross_after_fees_usd} />
          <p className="lede">Fee-adjusted revenue is not margin.</p>
        </Section>
      </div>
      <Section title="Needs attention">
        {recs.length ? (
          recs.slice(0, 12).map((r: any) => (
            <div
              key={r.sku}
              className="row"
              data-testid={`attention-${r.sku}`}
              onClick={() => onOpenSku(r.sku)}
            >
              <span>
                <strong>{r.sku}</strong> {r.action || r.attention_reason}
              </span>
              <span className="lede" style={{ margin: 0 }}>{r.why}</span>
            </div>
          ))
        ) : (
          <p className="lede">No attention items.</p>
        )}
      </Section>
    </div>
  );
}
