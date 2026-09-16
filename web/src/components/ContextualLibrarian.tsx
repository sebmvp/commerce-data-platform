import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { Sparkles } from "lucide-react";
import { ErrorNote } from "@/App";
import { LibrarianAnswer } from "@/components/LibrarianAnswer";
import { useAskLibrarian, useItem } from "@/lib/api";
import type { ContextObject, LibrarianResponse } from "@/types";

/**
 * Contextual Librarian: one question, one answer, replace on next ask.
 * Mounted on the object panel (`?ask=1`); object stays visible beside it.
 */
export function ContextualLibrarian({
  sku,
  attentionReason,
}: {
  sku: string;
  attentionReason: string | null;
}) {
  const ask = useAskLibrarian();
  const item = useItem(sku);
  const priceReview = attentionReason === "stale_listing" || attentionReason === "high_attention_no_offers";
  const prefill =
    priceReview && !window.sessionStorage.getItem(`librarian:last:${sku}`)
      ? "Should I review the price of this listing?"
      : "";
  const [question, setQuestion] = useState(prefill);
  const [result, setResult] = useState<LibrarianResponse | null>(null);
  const name = item.data?.data?.item?.product
    ? String(item.data.data.item.product)
    : sku;

  useEffect(() => {
    const last = window.sessionStorage.getItem(`librarian:last:${sku}`);
    if (last) {
      try {
        const parsed = JSON.parse(last) as { question: string; result: LibrarianResponse };
        setQuestion(parsed.question);
        setResult(parsed.result);
      } catch {
        /* ignore stale cache */
      }
    }
  }, [sku]);

  async function run(q: string) {
    const trimmed = (q || "").trim();
    if (!trimmed) return;
    try {
      const data = await ask.mutateAsync({ question: trimmed, sku });
      setResult(data);
      window.sessionStorage.setItem(
        `librarian:last:${sku}`,
        JSON.stringify({ question: trimmed, result: data }),
      );
    } catch {
      /* ErrorNote below renders ask.error */
    }
  }

  return (
    <div className="rounded border p-3" style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}>
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <span className="text-[12px]" style={{ color: "var(--text-secondary)" }}>
          Asking about{" "}
          <span className="font-medium" style={{ color: "var(--text-primary)" }}>
            {name}
          </span>
        </span>
        <Link
          to="/inventory/$sku"
          params={{ sku }}
          className="text-[11.5px] focus-ring underline-offset-2 hover:underline"
          style={{ color: "var(--accent-link)" }}
        >
          full workspace
        </Link>
      </div>

      <form
        className="flex gap-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          void run(question);
        }}
      >
        <input
          data-testid="question-input"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about this item"
          className="min-w-0 flex-1 rounded border px-2.5 py-1.5 text-[13.5px] focus-ring"
          style={{ background: "var(--surface-2)", borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}
        />
        <button
          type="submit"
          disabled={ask.isPending}
          className="flex shrink-0 items-center gap-1 rounded border px-2.5 py-1.5 text-[12.5px] font-medium focus-ring disabled:opacity-50"
          style={{ borderColor: "var(--accent-primary)", color: "var(--accent-faint)" }}
        >
          <Sparkles size={12} /> Ask
        </button>
      </form>

      {ask.isError ? (
        <div className="mt-2">
          <ErrorNote error={ask.error} retry={() => void run(question)} />
        </div>
      ) : null}

      {ask.isPending ? (
        <p className="mt-2.5 text-[12.5px]" data-testid="assembling" style={{ color: "var(--text-muted)" }}>
          Assembling business context…
        </p>
      ) : null}

      {result?.bundle ? (
        <div className="mt-3">
          <LibrarianAnswer
            answer={result}
            bundle={result.bundle}
            objects={(result.bundle.objects || []) as ContextObject[]}
            compact
          />
        </div>
      ) : null}
    </div>
  );
}
