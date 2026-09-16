import { useEffect, useState } from "react";
import { Link, useParams, useRouter } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { ErrorNote } from "@/App";
import { LibrarianAnswer } from "@/components/LibrarianAnswer";
import { useAskLibrarian, keys, useItem } from "@/lib/api";
import type { ContextBundle, ContextObject, LibrarianResponse } from "@/types";

const SAMPLES = [
  "What should I focus on today?",
  "What changed since the last snapshot?",
  "Which listings have interest but no offers?",
];

/**
 * Business Librarian full workspace. Synthesis surface — not search, not a
 * chat thread. `/librarian/$sku` binds the workspace to one object.
 */
export function LibrarianPage() {
  const params = useParams({ strict: false }) as { sku?: string };
  const sku = params?.sku || null;
  const item = useItem(sku);
  const ask = useAskLibrarian();
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<LibrarianResponse | null>(null);
  const qc = useQueryClient();

  // Keep-last question/answer per binding (session restart clears).
  useEffect(() => {
    const last = window.sessionStorage.getItem(`librarian:last:${sku || "unbound"}`);
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
      const data = await ask.mutateAsync({ question: trimmed, sku: sku || undefined });
      setResult(data);
      window.sessionStorage.setItem(
        `librarian:last:${sku || "unbound"}`,
        JSON.stringify({ question: trimmed, result: data }),
      );
    } catch {
      /* ErrorNote below renders ask.error */
    }
  }

  const bundle: ContextBundle | null = result?.bundle || null;
  const router = useRouter();
  const openObject = (obj: ContextObject) => {
    if (obj.type !== "Item") return;
    void qc.invalidateQueries({ queryKey: keys.item(obj.id) });
    void router.navigate({ to: "/inventory/$sku", params: { sku: obj.id } });
  };

  return (
    <div className="mx-auto max-w-6xl px-6 py-5" data-testid="librarian-page">
      <header className="mb-3">
        <h1 className="text-[18px] font-semibold tracking-tight">Business Librarian</h1>
        <p className="mt-0.5 max-w-[62ch] text-[13px]" style={{ color: "var(--text-muted)" }}>
          Ask a business question. The Librarian answers only when the required
          evidence is present.
        </p>
        {sku ? (
          <div
            className="mt-2 flex items-center gap-2 text-[13px]"
            data-testid="bound-object"
          >
            <span style={{ color: "var(--text-muted)" }}>Asking about</span>
            <Link
              to="/inventory/$sku"
              params={{ sku: sku as string }}
              data-testid="bound-chip"
              className="font-medium focus-ring underline-offset-2 hover:underline"
              style={{ color: "var(--accent-link)" }}
            >
              {item.data?.data?.item?.product
                ? String(item.data.data.item.product)
                : sku}
            </Link>
            <Link
              to="/inventory/$sku"
              params={{ sku: sku as string }}
              className="text-[12px] focus-ring underline-offset-2 hover:underline"
              style={{ color: "var(--text-muted)" }}
            >
              open in Inventory
            </Link>
          </div>
        ) : null}
      </header>

      <form
        className="mb-2 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void run(question);
        }}
      >
        <input
          data-testid="question-input"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask the Business Librarian"
          className="flex-1 rounded border px-3 py-2 text-[14px] focus-ring"
          style={{
            background: "var(--surface-1)",
            borderColor: "var(--border-subtle)",
            color: "var(--text-primary)",
          }}
        />
        <button
          type="submit"
          disabled={ask.isPending}
          className="flex items-center gap-1.5 rounded border px-3.5 py-2 text-[13.5px] font-medium focus-ring disabled:opacity-50"
          style={{
            borderColor: "var(--accent-primary)",
            color: "var(--accent-faint)",
            background: "var(--surface-1)",
          }}
        >
          <Sparkles size={14} /> Ask
        </button>
      </form>

      {!sku && !result ? (
        <div className="mb-3 flex flex-wrap gap-1.5">
          {SAMPLES.map((s) => (
            <button
              key={s}
              className="rounded border px-2 py-1 text-[12.5px] focus-ring"
              style={{ borderColor: "var(--border-subtle)", color: "var(--text-muted)" }}
              onClick={() => {
                setQuestion(s);
                void run(s);
              }}
            >
              {s}
            </button>
          ))}
        </div>
      ) : null}

      {ask.isError ? (
        <ErrorNote error={ask.error} retry={() => void run(question)} />
      ) : null}

      {ask.isPending ? (
        <div className="py-3" data-testid="assembling">
          <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
            Assembling business context…
          </p>
        </div>
      ) : null}

      {bundle ? (
        <AnswerArea answer={result} bundle={bundle} onOpenObject={openObject} />
      ) : null}
    </div>
  );
}

function AnswerArea({
  answer,
  bundle,
  onOpenObject,
}: {
  answer: LibrarianResponse | null;
  bundle: ContextBundle;
  onOpenObject: (o: ContextObject) => void;
}) {
  return (
    <div className="mt-3">
      <LibrarianAnswer
        answer={answer}
        bundle={bundle}
        objects={(bundle.objects || []) as ContextObject[]}
        onOpenObject={onOpenObject}
      />
    </div>
  );
}
