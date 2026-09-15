import { useState } from "react";
import { Field, Section, StatusChip } from "@/components/primitives";
import { formatMoney } from "@/lib/format";
import {
  useDecideAction,
  useListActions,
  useProposeAction,
  useSuggestAction,
} from "@/lib/api";
import type { ActionRecord } from "@/types";

/**
 * Sandbox-only reprice loop: propose → approve/reject → applied internally.
 * No marketplace writes; the sandbox applies listing_events only.
 */
export function ActionPanel({ sku, onChanged }: { sku: string; onChanged?: () => void }) {
  const [price, setPrice] = useState("");
  const [error, setError] = useState<string | null>(null);
  const actions = useListActions(sku);
  const suggest = useSuggestAction(sku);
  const propose = useProposeAction();
  const decide = useDecideAction();

  const history = actions.data?.data?.actions || [];
  const pending = history.find((a) => a.status === "proposed") || null;
  const applied = history.find((a) => a.status === "applied") || null;
  const suggestion = suggest.data?.data ?? null;
  const evidence = (suggestion?.evidence as Record<string, unknown> | undefined) || {};

  async function onPropose(e: React.FormEvent) {
    e.preventDefault();
    if (!suggestion) return;
    const entered = Number(price);
    if (!Number.isFinite(entered) || entered <= 0) {
      setError("Enter a positive sandbox price.");
      return;
    }
    setError(null);
    try {
      await propose.mutateAsync({
        target_type: "item",
        target_id: sku,
        action_type: String(suggestion.action_type || ""),
        reason: String(suggestion.reason || ""),
        payload: {
          ...((suggestion.payload && typeof suggestion.payload === "object"
            ? suggestion.payload
            : {}) as Record<string, unknown>),
          sku,
          listing_id: suggestion.target_id,
          new_price_usd: entered,
        },
        recommendation_action: "consider_reprice",
        context_question: `Should I reprice ${sku}?`,
        supporting_context: evidence,
      });
      onChanged?.();
    } catch (err) {
      setError(String(err));
    }
  }

  async function onDecide(kind: "approve" | "reject", record: ActionRecord) {
    setError(null);
    try {
      await decide.mutateAsync({
        actionId: record.action_id,
        kind,
        reason: kind === "reject" ? "operator declined" : undefined,
      });
      onChanged?.();
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <Section title="Sandbox action" testId="action-panel" tone="inset">
      <p className="mb-2 text-[12.5px]" style={{ color: "var(--text-muted)" }}>
        Internal sandbox only. Approval records internal events — it never changes a marketplace listing.
      </p>
      {error ? <p className="err mb-2 text-[13px]" style={{ color: "var(--danger)" }}>{error}</p> : null}

      {suggest.isPending ? (
        <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
          Loading suggestion…
        </p>
      ) : suggestion && !pending ? (
        <>
          <p className="text-[13.5px]" style={{ color: "var(--text-secondary)" }} data-testid="price-review">
            {String(suggestion.reason || "")}
          </p>
          <div className="mt-1.5">
            <Field label="current ask" value={formatMoney(evidence.asking_price_usd, "USD")} />
            <Field label="why" value={String(evidence.note ?? "")} />
          </div>
          <form onSubmit={onPropose} className="mt-2 flex gap-2">
            <input
              data-testid="sandbox-price"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="sandbox price USD"
              inputMode="decimal"
              className="w-40 rounded border px-2 py-1.5 text-[13.5px] focus-ring"
              style={{ background: "var(--surface-2)", borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}
            />
            <button
              data-testid="propose-action"
              disabled={propose.isPending}
              className="rounded border px-3 py-1.5 text-[13.5px] font-medium focus-ring disabled:opacity-50"
              style={{ borderColor: "var(--accent-primary)", color: "var(--accent-faint)" }}
            >
              Propose reprice
            </button>
          </form>
        </>
      ) : null}

      {pending ? (
        <div data-testid="pending-action">
          <div className="flex items-center gap-2">
            <StatusChip tone="warn">proposed</StatusChip>
            <span className="tabular text-[14px]" style={{ color: "var(--text-primary)" }}>
              {String(pending.proposed_payload?.previous_price_usd ?? "")} → {String(pending.proposed_payload?.new_price_usd ?? "")}
            </span>
          </div>
          <div className="mt-2 flex gap-2">
            <button
              data-testid="approve-action"
              disabled={decide.isPending}
              onClick={() => void onDecide("approve", pending)}
              className="rounded border px-3 py-1.5 text-[13.5px] font-medium focus-ring disabled:opacity-50"
              style={{ borderColor: "#14532d", color: "var(--success)" }}
            >
              Approve
            </button>
            <button
              data-testid="reject-action"
              disabled={decide.isPending}
              onClick={() => void onDecide("reject", pending)}
              className="rounded border px-3 py-1.5 text-[13.5px] focus-ring disabled:opacity-50"
              style={{ borderColor: "var(--border-subtle)", color: "var(--text-secondary)" }}
            >
              Reject
            </button>
          </div>
        </div>
      ) : null}

      {applied ? (
        <p data-testid="applied-action" className="text-[13.5px]" style={{ color: "var(--success)" }}>
          Applied in sandbox
          {applied.resulting_value?.price_usd != null ? ` → $${applied.resulting_value.price_usd}` : ""}
        </p>
      ) : null}
      {decide.isSuccess && !applied ? (
        <p className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
          Sandbox decision recorded.
        </p>
      ) : null}
    </Section>
  );
}
