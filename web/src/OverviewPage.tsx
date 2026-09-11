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
                <strong>{r.sku}</strong>
              </span>
              <span className="lede" style={{ margin: 0 }}>{r.why || r.action || r.attention_reason}</span>
            </div>
          ))
        ) : (
          <p className="lede">No attention items.</p>
        )}
      </Section>
      <div className="grid">
        <Section title="Inventory state">
          <Field label="items" value={data.items_total} />
          <Field label="owned unlisted" value={data.owned_unlisted} />
          <Field label="listed" value={data.listed_items} />
          <Field label="sold" value={data.sold_items} />
        </Section>
        <Section title="Capital">
          <Field label="capital tied up CNY" value={data.capital_tied_up_cny} />
          <Field label="USD estimate (display FX)" value={data.capital_tied_up_usd_est} />
          <p className="lede">Fee-adjusted revenue is not margin.</p>
        </Section>
      </div>
    </div>
  );
}
