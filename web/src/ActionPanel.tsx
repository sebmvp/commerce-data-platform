import { useEffect, useState } from "react";
import {
  approveAction,
  getSuggestAction,
  listActions,
  proposeAction,
  rejectAction,
} from "./api";
import { Field, Section } from "./ui";

export function ActionPanel({
  sku,
  onApplied,
}: {
  sku: string;
  onApplied: () => void;
}) {
  const [suggestion, setSuggestion] = useState<any>(null);
  const [pending, setPending] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [price, setPrice] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      const listed = await listActions(sku);
      const actions = listed.data?.actions || [];
      setHistory(actions);
      setPending(actions.find((a: any) => a.status === "proposed") || null);
    } catch {
      setHistory([]);
    }
    try {
      const sug = await getSuggestAction(sku);
      setSuggestion(sug.data);
    } catch {
      setSuggestion(null);
    }
  }

  useEffect(() => {
    void refresh();
  }, [sku]);

  async function propose() {
    if (!suggestion) return;
    const entered = Number(price);
    if (!Number.isFinite(entered) || entered <= 0) {
      setError("Enter a positive sandbox price.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await proposeAction({
        target_type: "item",
        target_id: sku,
        action_type: suggestion.action_type,
        reason: suggestion.reason,
        payload: {
          ...(suggestion.payload || {}),
          sku,
          listing_id: suggestion.target_id,
          new_price_usd: entered,
        },
        recommendation_action: "consider_reprice",
        context_question: `Should I reprice ${sku}?`,
        supporting_context: suggestion.evidence || {},
      });
      setPending(created.data || created);
      await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function decide(kind: "approve" | "reject") {
    if (!pending) return;
    setBusy(true);
    setError(null);
    try {
      if (kind === "approve") await approveAction(pending.action_id);
      else await rejectAction(pending.action_id, "operator declined");
      await refresh();
      onApplied();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  const evidence = suggestion?.evidence || {};
  const applied = history.find((a) => a.status === "applied");

  return (
    <Section title="Sandbox action" testId="action-panel">
      <p className="lede">
        Internal sandbox only. Approval does not change a marketplace listing.
      </p>
      {error && <p className="err">{error}</p>}
      {suggestion && !pending && (
        <>
          <p data-testid="price-review">{suggestion.reason}</p>
          <Field label="current ask" value={evidence.asking_price_usd} />
          <Field label="why" value={evidence.note} />
          <form
            className="ask"
            onSubmit={(e) => {
              e.preventDefault();
              void propose();
            }}
          >
            <input
              data-testid="sandbox-price"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="sandbox price USD"
            />
            <button data-testid="propose-action" className="obj-link" disabled={busy} type="submit">
              Propose reprice
            </button>
          </form>
        </>
      )}
      {pending && (
        <div data-testid="pending-action">
          <p>
            Reprice {pending.proposed_payload?.previous_price_usd} → {pending.proposed_payload?.new_price_usd}
          </p>
          <button data-testid="approve-action" className="obj-link" disabled={busy} onClick={() => void decide("approve")}>
            Approve
          </button>{" "}
          <button data-testid="reject-action" className="obj-link" disabled={busy} onClick={() => void decide("reject")}>
            Reject
          </button>
        </div>
      )}
      {applied && (
        <p data-testid="applied-action" className="pass">
          Applied in sandbox {applied.resulting_value?.price_usd != null ? `→ ${applied.resulting_value.price_usd}` : ""}
        </p>
      )}
    </Section>
  );
}
