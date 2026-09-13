import type { AttentionQueue, BusinessSnapshot } from "./types";
import {
  attentionAction,
  attentionMeta,
  formatMoney,
  observedDate,
  rankAttention,
} from "./format";
import { Field, Section } from "./ui";

export function OverviewPage({
  snapshot,
  attention,
  changes,
  loading,
  onOpenSku,
}: {
  snapshot: BusinessSnapshot | null;
  attention: AttentionQueue | null;
  changes: Array<{ label: string; detail: string }>;
  loading?: boolean;
  onOpenSku: (sku: string) => void;
}) {
  const data = snapshot?.data || {};
  const queue = rankAttention(attention?.data?.queue || []);
  const asOf = observedDate(String(snapshot?.provenance?.as_of || data.as_of || "")) || "—";
  return (
    <div data-testid="overview-page" className="overview-layout">
      <Section title="Needs attention">
        {loading && !queue.length ? (
          <p className="empty">Loading attention…</p>
        ) : queue.length ? (
          queue.map((r) => (
            <div
              key={r.sku}
              className="attention-row"
              data-testid={`attention-${r.sku}`}
              onClick={() => onOpenSku(r.sku)}
            >
              <div>
                <div className="attention-name">{r.product || "Item"}</div>
                <div className="attention-meta">{attentionMeta(r)}</div>
              </div>
              <div className="attention-action">{attentionAction(r.attention_reason)}</div>
            </div>
          ))
        ) : (
          <p className="empty">Nothing in the attention queue.</p>
        )}
      </Section>
      <div className="overview-side">
        <Section title="Inventory">
          <div data-testid="overview-items-total">
            <Field label="items" value={data.items_total} />
          </div>
          <Field label="unlisted" value={data.owned_unlisted} />
          <Field label="listed" value={data.listed_items} />
          <Field label="sold" value={data.sold_items} />
        </Section>
        <Section title="Capital">
          <Field label="tied up" value={formatMoney(data.capital_tied_up_cny, "CNY")} />
          <Field label="USD est." value={formatMoney(data.capital_tied_up_usd_est, "USD")} />
          <p className="lede tight">Fee-adjusted revenue is not margin.</p>
        </Section>
        <Section title="Recent changes" testId="recent-changes">
          {changes.length ? (
            changes.map((row) => (
              <div key={row.label} className="row">
                <span>{row.label}</span>
                <span className="dim">{row.detail}</span>
              </div>
            ))
          ) : (
            <p className="empty">{loading ? "Loading…" : "No snapshot deltas in the lookback window."}</p>
          )}
        </Section>
        <Section title="Freshness">
          <Field label="stale listings" value={data.stale_active_listings} />
          <Field label="as of" value={asOf} />
        </Section>
      </div>
    </div>
  );
}
