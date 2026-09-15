import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ArrowRight, ListChecks } from "lucide-react";
import { LoadingDots, ErrorNote } from "@/App";
import { Section, StatusChip } from "@/components/primitives";
import {
  attentionAction,
  attentionMeta,
  attentionTone,
  formatMoney,
  observedDate,
  rankAttention,
} from "@/lib/format";
import type { AttentionQueueRow } from "@/types";
import { useAttention, useRecentChanges, useSnapshot } from "@/lib/api";

export function OverviewPage() {
  return (
    <div className="mx-auto max-w-6xl px-5 py-4" data-testid="overview-page">
      <header className="mb-4">
        <h1 className="text-[17px] font-semibold tracking-tight">Overview</h1>
        <p className="mt-0.5 text-[13px]" style={{ color: "var(--text-muted)" }}>
          What needs attention, what the business state is, what changed.
        </p>
      </header>
      <OverviewBody />
    </div>
  );
}

function OverviewBody() {
  // Composed below once queries exist; keeps page shell testable.
  return <AttentionFirst />;
}

function AttentionFirst() {
  const snapshot = useSnapshot();
  const attention = useAttention();
  const changes = useRecentChanges();
  const qc = useQueryClient();

  // Prefetch inventory so opening rows later is instant.
  useEffect(() => {
    void qc.prefetchQuery({
      queryKey: ["inventory", "all"],
      queryFn: async () => {
        const res = await fetch("http://127.0.0.1:8000/inventory/items");
        return res.json();
      },
    });
  }, [qc]);

  if (snapshot.isError) {
    return <ErrorNote error={snapshot.error} retry={() => void snapshot.refetch()} />;
  }
  const data = snapshot.data?.data || {};
  const queue = rankAttention(attention.data?.data?.queue || []);
  const asOf =
    observedDate(String(snapshot.data?.provenance?.as_of || data.as_of || "")) || "—";

  return (
    <div className="grid grid-cols-[minmax(0,1.55fr)_minmax(260px,0.9fr)] gap-6 max-[1100px]:grid-cols-1">
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="section-label flex items-center gap-1.5">
            <ListChecks size={13} /> Needs attention
            {attention.data?.data?.queue?.length ? (
              <span style={{ color: "var(--text-secondary)" }}>
                {attention.data.data.queue.length}
              </span>
            ) : null}
          </h2>
          <span className="text-[12px]" style={{ color: "var(--text-muted)" }}>
            as of {asOf}
          </span>
        </div>
        {snapshot.isPending || attention.isPending ? (
          <AttentionSkeleton />
        ) : (
          <div>
            {queue.map((row: AttentionQueueRow, i: number) => (
              <Link
                key={`${row.sku}-${i}`}
                to="/inventory/$sku"
                params={{ sku: row.sku }}
                data-testid={`attention-${row.sku}`}
                className="group grid grid-cols-[1fr_auto] items-center gap-3 border-b py-2.5 first:border-t focus-ring"
                style={{ borderColor: "var(--border-subtle)" }}
              >
                <div className="min-w-0">
                  <div className="flex items-baseline gap-2">
                    <span className="truncate text-[14px] font-medium" style={{ color: "var(--text-primary)" }}>
                      {row.product || row.sku}
                    </span>
                    <StatusChip tone={attentionTone(row.attention_reason)}>
                      {attentionAction(row.attention_reason)}
                    </StatusChip>
                  </div>
                  <div className="mt-0.5 text-[12.5px]" style={{ color: "var(--text-muted)" }}>
                    {attentionMeta(row)}
                  </div>
                </div>
                <ArrowRight
                  size={15}
                  className="opacity-0 transition-opacity group-hover:opacity-100"
                  style={{ color: "var(--accent-support)" }}
                />
              </Link>
            ))}
            {!queue.length ? (
              <p className="py-6 text-center text-[13.5px]" style={{ color: "var(--text-muted)" }}>
                Nothing in the attention queue.
              </p>
            ) : null}
          </div>
        )}
      </div>

      <div className="space-y-5">
        <Section title="Business state">
          <div className="grid grid-cols-4 gap-3 max-[420px]:grid-cols-2">
            <Metric label="Items" value={data.items_total} />
            <Metric label="Unlisted" value={data.owned_unlisted} />
            <Metric label="Listed" value={data.listed_items} />
            <Metric label="Sold" value={data.sold_items} />
          </div>
          <div className="mt-3 border-t pt-3" style={{ borderColor: "var(--border-subtle)" }}>
            <div className="grid grid-cols-2 gap-3">
              <Metric
                label="Capital tied up"
                value={formatMoney(data.capital_tied_up_cny, "CNY")}
                large
              />
              <Metric label="USD est." value={formatMoney(data.capital_tied_up_usd_est, "USD")} large />
            </div>
            <p className="mt-1.5 text-[12px]" style={{ color: "var(--text-muted)" }}>
              Fee-adjusted revenue is not margin.
            </p>
          </div>
        </Section>

        <Section title="Recent changes" testId="recent-changes">
          {changes.isPending ? (
            <LoadingDots label="Loading changes…" />
          ) : changes.data?.length ? (
            <div>
              {changes.data.map((row) => (
                <div
                  key={row.label}
                  className="flex items-baseline justify-between gap-3 border-b py-1.5 last:border-0"
                  style={{ borderColor: "var(--border-subtle)" }}
                >
                  <span className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
                    {row.label}
                  </span>
                  <span className="tabular text-[12.5px]" style={{ color: "var(--text-muted)" }}>
                    {row.detail}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
              No snapshot deltas in the lookback window.
            </p>
          )}
        </Section>

        <Section title="Freshness">
          <p className="tabular text-[13.5px]" style={{ color: "var(--text-secondary)" }}>
            <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
              {data.stale_active_listings ?? "—"}
            </span>{" "}
            stale listings · as of {asOf}
          </p>
        </Section>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  large,
}: {
  label: string;
  value: unknown;
  large?: boolean;
}) {
  return (
    <div>
      <div className="section-label">{label}</div>
      <div
        className={"tabular tracking-tight " + (large ? "text-[19px] font-semibold" : "text-[16px] font-semibold")}
        style={{ color: value == null ? "var(--text-muted)" : "var(--text-primary)" }}
      >
        {value == null || value === "" ? "—" : String(value)}
      </div>
    </div>
  );
}

function AttentionSkeleton() {
  return (
    <div aria-hidden className="space-y-2.5 py-1">
      {[...Array(6)].map((_, i) => (
        <div key={i} className="animate-pulse space-y-1.5">
          <div className="h-3.5 w-2/5 rounded" style={{ background: "var(--surface-2)" }} />
          <div className="h-2.5 w-1/4 rounded" style={{ background: "var(--surface-1)" }} />
        </div>
      ))}
    </div>
  );
}
