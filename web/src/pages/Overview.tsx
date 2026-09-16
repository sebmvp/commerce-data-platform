import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ArrowRight, ListChecks } from "lucide-react";
import { LoadingDots, ErrorNote } from "@/App";
import { StatusChip } from "@/components/primitives";
import {
  attentionAction,
  attentionMeta,
  attentionTone,
  attentionRowKey,
  channelName,
  formatMoney,
  observedDate,
  rankAttention,
} from "@/lib/format";
import type { AttentionQueueRow } from "@/types";
import { useAttention, useRecentChanges, useSnapshot } from "@/lib/api";

/**
 * Command Center — management by exception. First two seconds answer:
 * what needs a decision, what moved, can I trust the books.
 */
export function CommandCenterPage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-5" data-testid="command-center-page">
      <header className="mb-5 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-[18px] font-semibold tracking-tight">Command Center</h1>
          <p className="mt-0.5 text-[13px]" style={{ color: "var(--text-muted)" }}>
            What needs a decision, what moved, whether the books are fresh.
          </p>
        </div>
      </header>
      <CommandCenterBody />
    </div>
  );
}

function CommandCenterBody() {
  const snapshot = useSnapshot();
  const attention = useAttention();
  const changes = useRecentChanges();
  const qc = useQueryClient();

  // Prefetch inventory so opening rows later is instant.
  useEffect(() => {
    void qc.prefetchQuery({ queryKey: ["inventory", "all"] });
  }, [qc]);

  if (snapshot.isError) {
    return <ErrorNote error={snapshot.error} retry={() => void snapshot.refetch()} />;
  }
  const data = snapshot.data?.data || {};
  const fullQueue = attention.data?.data?.queue || [];
  const queue = rankAttention(fullQueue);
  const unlisted = fullQueue.filter(
    (r: AttentionQueueRow) => r.attention_reason === "unlisted_owned",
  ).length;
  const asOf =
    observedDate(String(snapshot.data?.provenance?.as_of || data.as_of || "")) || "—";
  const pending = snapshot.isPending || attention.isPending;

  return (
    <div className="space-y-6">
      {/* Needs a decision — the only heavy surface on this page */}
      <section data-testid="needs-decision">
        <div className="mb-2 flex items-baseline justify-between gap-3">
          <h2 className="section-label flex items-center gap-1.5">
            <ListChecks size={13} /> Needs a decision
            <span className="tabular" style={{ color: "var(--text-secondary)" }}>
              {pending ? "" : `${queue.length} of ${fullQueue.length}`}
            </span>
          </h2>
          <span className="tabular text-[12px]" style={{ color: "var(--text-muted)" }}>
            as of {asOf}
          </span>
        </div>
        {pending ? (
          <AttentionSkeleton />
        ) : (
          <div className="rounded border" style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}>
            {queue.map((row: AttentionQueueRow) => (
              <Link
                key={attentionRowKey(row)}
                to="/inventory/$sku"
                params={{ sku: row.sku }}
                data-testid={`attention-${row.sku}`}
                className="group grid grid-cols-[1fr_auto] items-center gap-3 border-b px-4 py-2.5 last:border-b-0 focus-ring"
                style={{ borderColor: "var(--border-subtle)" }}
              >
                <div className="min-w-0">
                  <div className="flex items-baseline gap-2">
                    <span
                      className="truncate text-[14.5px] font-medium"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {row.product || row.sku}
                    </span>
                    <StatusChip tone={attentionTone(row.attention_reason)}>
                      {attentionAction(row.attention_reason)}
                    </StatusChip>
                  </div>
                  <div className="tabular mt-0.5 text-[12.5px]" style={{ color: "var(--text-muted)" }}>
                    {attentionMeta(row)}
                  </div>
                </div>
                <div className="flex shrink-0 items-baseline gap-3">
                  <div className="tabular text-right text-[12.5px]">
                    {row.platform ? (
                      <div style={{ color: "var(--text-secondary)" }}>
                        {channelName(row.platform)}
                        {row.listing_price_usd != null ? ` · ${formatMoney(row.listing_price_usd, "USD")}` : ""}
                      </div>
                    ) : null}
                    {row.acquisition_cost_cny != null ? (
                      <div style={{ color: "var(--text-muted)" }}>
                        cost {formatMoney(row.acquisition_cost_cny, "CNY")}
                      </div>
                    ) : null}
                  </div>
                  <ArrowRight
                    size={15}
                    className="opacity-0 transition-opacity group-hover:opacity-100"
                    style={{ color: "var(--accent-support)" }}
                  />
                </div>
              </Link>
            ))}
            {!queue.length ? (
              <p className="px-4 py-6 text-[13.5px]" style={{ color: "var(--text-muted)" }}>
                Nothing needs a decision.
              </p>
            ) : null}
            {unlisted > 0 ? (
              <div
                className="px-4 py-2.5 text-[12.5px]"
                style={{ color: "var(--text-muted)", borderTop: "1px solid var(--border-subtle)" }}
              >
                <Link
                  to="/inventory"
                  search={{ status: "owned" }}
                  className="focus-ring underline-offset-2 hover:underline"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {unlisted} owned items are unlisted — that is pulse, not {unlisted} exceptions.
                </Link>{" "}
                View all in Inventory →
              </div>
            ) : null}
          </div>
        )}
      </section>

      {/* Pulse — one quiet hairline row, not a KPI wall */}
      <section data-testid="pulse">
        <div className="section-label mb-1.5">Pulse</div>
        <div className="flex flex-wrap items-baseline gap-x-5 gap-y-1 border-y py-3" style={{ borderColor: "var(--border-subtle)" }}>
          <PulseStat label="Items" value={data.items_total} />
          <PulseStat label="Listed" value={data.listed_items} />
          <PulseStat label="Unlisted" value={data.owned_unlisted} />
          <PulseStat label="Sold" value={data.sold_items} />
          <span className="tabular text-[13px]" style={{ color: "var(--text-muted)" }}>
            {data.stale_active_listings ?? "—"} stale listings
          </span>
          <span className="tabular ml-auto text-[15px] font-semibold" style={{ color: "var(--text-primary)" }}>
            {formatMoney(data.capital_tied_up_cny, "CNY")}
            {data.capital_tied_up_usd_est != null ? (
              <span className="tabular ml-1.5 text-[12.5px] font-normal" style={{ color: "var(--text-muted)" }}>
                (USD est. {formatMoney(data.capital_tied_up_usd_est, "USD")})
              </span>
            ) : null}
          </span>
        </div>
        <p className="mt-1 flex flex-wrap items-center gap-x-2 text-[12.5px]" style={{ color: "var(--text-muted)" }}>
          <span>Fee-adjusted revenue is not margin.</span>
          {trustHelper(snapshot.data?.data)}
          <span className="tabular">ingest reconciled · as of {asOf}</span>
        </p>
      </section>

      {/* Recent changes — the deltas the operator already produced */}
      <section data-testid="recent-changes">
        <div className="section-label mb-1.5">Recent changes</div>
        {changes.isPending ? (
          <LoadingDots label="Loading changes…" />
        ) : changes.data?.length ? (
          <div className="flex flex-wrap gap-x-6 gap-y-1">
            {changes.data.map((row) => (
              <span key={row.label} className="tabular text-[13px]">
                <span style={{ color: "var(--text-secondary)" }}>{row.label}</span>{" "}
                <span style={{ color: "var(--text-muted)" }}>{row.detail}</span>
              </span>
            ))}
          </div>
        ) : (
          <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
            No snapshot deltas in the lookback window.
          </p>
        )}
      </section>
    </div>
  );
}

function PulseStat({ label, value }: { label: string; value: unknown }) {
  return (
    <span className="tabular text-[13px]">
      <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
        {value == null || value === "" ? "—" : String(value)}
      </span>{" "}
      <span style={{ color: "var(--text-muted)" }}>{label.toLowerCase()}</span>
    </span>
  );
}

function trustHelper(data: Record<string, unknown> | undefined): string | null {
  if (!data) return null;
  return data.warehouse_trust_ok === false ? "trust NOT OK ·" : "trust OK ·";
}

function AttentionSkeleton() {
  return (
    <div aria-hidden className="space-y-2.5 p-4">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="animate-pulse space-y-1.5">
          <div className="h-3.5 w-2/5 rounded" style={{ background: "var(--surface-2)" }} />
          <div className="h-2.5 w-1/4 rounded" style={{ background: "var(--surface-1)" }} />
        </div>
      ))}
    </div>
  );
}
