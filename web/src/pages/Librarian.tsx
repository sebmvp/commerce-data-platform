import { useEffect, useState } from "react";
import { Link, useParams, useRouter } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { ErrorNote, LoadingDots } from "@/App";
import { Field, Section, StatusChip } from "@/components/primitives";
import { decisiveCards, humanLabel, observedDate, relVerb, whyText, typeLabel } from "@/lib/format";
import { keys, useAskLibrarian, useItem } from "@/lib/api";
import type { ContextBundle, ContextObject, LibrarianResponse } from "@/types";

const SAMPLES = [
  "Should I review the price of this listing?",
  "What should I focus on today?",
  "What was the active listing state for j4-military-s two weeks ago?",
];

export function LibrarianPage() {
  const params = useParams({ strict: false }) as { sku?: string };
  const sku = params?.sku || null;
  const item = useItem(sku);
  const ask = useAskLibrarian();
  const [question, setQuestion] = useState(() =>
    sku ? "Should I review the price of this listing?" : "",
  );
  const [result, setResult] = useState<LibrarianResponse | null>(null);
  const qc = useQueryClient();

  // laatst gestelde vraag per object blijft in de URL-parameters herleidbaar
  useEffect(() => {
    const last = window.sessionStorage.getItem(`librarian:last:${sku || "unbound"}`);
    if (last) {
      const parsed = JSON.parse(last) as { question: string; result: LibrarianResponse };
      setQuestion(parsed.question);
      setResult(parsed.result);
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
      // error_surface below renders ask.error
    }
  }

  const bundle = result?.bundle || null;
  const router = useRouter();
  const openObject = (obj: ContextObject) => {
    if (obj.type !== "Item") return;
    void qc.invalidateQueries({ queryKey: keys.item(obj.id) });
    void router.navigate({ to: "/inventory/$sku", params: { sku: obj.id } });
  };

  return (
    <div className="mx-auto max-w-6xl px-5 py-4" data-testid="librarian-page">
      <header className="mb-3 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-[17px] font-semibold tracking-tight">Business Librarian</h1>
          <p className="mt-0.5 max-w-[62ch] text-[13px]" style={{ color: "var(--text-muted)" }}>
            Maps a question to registered domain capabilities, assembles the required
            context, and answers only when that evidence is sufficient.
          </p>
        </div>
        {sku ? (
          <div className="flex items-center gap-2 text-[13px]" data-testid="bound-chip">
            <StatusChip tone="info">bound</StatusChip>
            <Link to="/inventory/$sku" params={{ sku: sku as string }} className="focus-ring underline-offset-2 hover:underline" style={{ color: "var(--accent-link)" }}>
              {item.data?.data?.item ? productName(item.data.data.item, sku) : sku}
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
          style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}
        />
        <button
          type="submit"
          disabled={ask.isPending}
          className="flex items-center gap-1.5 rounded border px-3.5 py-2 text-[13.5px] font-medium focus-ring disabled:opacity-50"
          style={{ borderColor: "var(--accent-primary)", color: "var(--accent-faint)", background: "var(--surface-1)" }}
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

      {ask.isError ? <ErrorNote error={ask.error} retry={() => void run(question)} /> : null}

      {ask.isPending ? (
        <div className="py-3" data-testid="assembling">
          <LoadingDots label="Assembling business context…" />
        </div>
      ) : null}

      {bundle ? (
        <AnswerView answer={result} bundle={bundle} onOpenObject={openObject} itemSku={sku} />
      ) : null}
    </div>
  );
}

function productName(itemData: Record<string, unknown>, fallback: string): string {
  return String(itemData.product || fallback);
}

function AnswerView({
  answer,
  bundle,
  onOpenObject,
  itemSku,
}: {
  answer: LibrarianResponse | null;
  bundle: ContextBundle;
  onOpenObject: (o: ContextObject) => void;
  itemSku?: string | null;
}) {
  const sufficient = bundle.sufficient;
  const plan = answer?.plan?.capability || bundle.intent;
  const observed = observedDate(bundle.as_of);
  const fake = answer?.provider === "fake" || answer?.provider_kind === "fake";
  const cards = decisiveCards(answer, bundle);
  const grounded = answer?.grounding_status === "grounded";
  const inactive = answer?.grounding_status === "invalid";
  const abstained = answer?.abstained || answer?.grounding_status === "abstained";

  return (
    <div className="mt-3 space-y-4">
      {/* Primary layer: verdict + answer + decisive evidence in one view */}
      <section
        className="rounded border p-4"
        data-testid="sufficiency"
        style={{
          background: "var(--surface-1)",
          borderColor: sufficient ? "#14532d" : "#7f1d1d",
        }}
      >
        {!abstained && answer ? (
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-baseline gap-2">
                <span
                  className="text-[15px] font-semibold tracking-tight"
                  style={{ color: grounded ? "var(--text-primary)" : inactive ? "var(--danger)" : "var(--text-secondary)" }}
                  data-testid="grounded-answer"
                >
                  {inactive ? "Invalid model output" : abstained ? "Abstained" : "Answer"}
                </span>
                <StatusChip tone={sufficient ? "ok" : "bad"}>{sufficient ? "sufficient" : "insufficient"}</StatusChip>
              </div>
              <p className="mt-1 max-w-[68ch] text-[14.5px]" style={{ color: "var(--text-primary)" }} data-testid="answer-text">
                {fake && !abstained
                  ? "Context is sufficient. Decisive evidence is below."
                  : answer.answer}
              </p>
              {fake ? (
                <p className="mt-1 text-[12px]" style={{ color: "var(--text-muted)" }}>
                  Test provider — extractive restatement, not model reasoning.
                </p>
              ) : null}
              {!!answer.caveats?.length ? (
                <p className="mt-1 text-[12.5px]" style={{ color: "var(--text-muted)" }}>
                  {answer.caveats.join(" · ")}
                </p>
              ) : null}
              {!!answer.suggested_action ? (
                <p className="mt-1.5 text-[13px]" data-testid="suggested-action" style={{ color: "var(--accent-support)" }}>
                  Proposed sandbox action: {humanLabel(answer.suggested_action.action_type)}
                  {answer.suggested_action.recommendation
                    ? ` · ${humanLabel(String(answer.suggested_action.recommendation))}`
                    : ""}{" "}
                  (human approval required)
                </p>
              ) : null}
            </div>
            <div className="hidden max-w-[280px] text-right lg:block">
              <div className="text-[11px] uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                {humanLabel(String(plan))} · as of {observed || bundle.as_of}
              </div>
              <p className="mt-0.5 text-[12.5px]" style={{ color: "var(--text-secondary)" }} data-testid="assembled-question">
                {bundle.question}
              </p>
            </div>
          </div>
        ) : (
          <p className="text-[14.5px]" style={{ color: "var(--text-secondary)" }}>
            {answer && inactive ? "Grounding rejected the model output." : "Context is not sufficient to answer — see what is missing below."}
          </p>
        )}

        <div className="mt-3 border-t pt-3" style={{ borderColor: "var(--border-subtle)" }}>
          <div className="section-label mb-1.5">Why</div>
          <p className="max-w-[70ch] text-[13.5px]" style={{ color: "var(--text-secondary)" }} data-testid="why">
            {whyText(bundle.why)}
          </p>
        </div>

        {/* Missing context is the honest failure surface, surfaced early */}
        {!!bundle.missing_context.length ? (
          <div
            className="mt-3 rounded border px-3 py-2.5"
            data-testid="missing-context"
            style={{ borderColor: "#7f1d1d", background: "#1a1014" }}
          >
            <div className="mb-1 flex items-baseline justify-between gap-3">
              <span className="text-[12.5px] font-medium" style={{ color: "var(--danger)" }}>
                Missing context
              </span>
              {itemSku ? (
                <Link
                  to="/inventory/$sku"
                  params={{ sku: itemSku }}
                  className="text-[12px] focus-ring underline-offset-2 hover:underline"
                  style={{ color: "var(--accent-link)" }}
                >
                  Inspect this object in Inventory
                </Link>
              ) : null}
            </div>
            <ul className="m-0 list-disc pl-5 text-[13px]" style={{ color: "var(--text-secondary)" }}>
              {bundle.missing_context.map((m) => (
                <li key={m.concept}>
                  <span style={{ color: "var(--text-primary)" }}>{humanLabel(m.concept)}</span> — {whyText(m.reason)}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      {cards.length ? (
        <section data-testid="cited-evidence">
          <div className="mb-1.5 flex items-baseline gap-2">
            <div className="section-label">Decisive evidence</div>
            {cards[0]?.source ? (
              <span className="text-[12px]" style={{ color: "var(--text-muted)" }}>
                {cards[0].source}
                {cards[0].observed ? ` · observed ${cards[0].observed}` : ""}
              </span>
            ) : null}
          </div>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(170px,1fr))] gap-2">
            {cards.map((card) => (
              <div
                key={card.label}
                className="rounded border px-2.5 py-2"
                style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}
              >
                <div className="section-label">{card.label}</div>
                <div className="tabular mt-0.5 text-[17px] font-semibold tracking-tight" style={{ color: "var(--text-primary)" }}>
                  {card.value}
                </div>
                {card.source && card.source !== cards[0]?.source ? (
                  <div className="mt-0.5 text-[12px]" style={{ color: "var(--text-muted)" }}>
                    {card.source}
                    {card.observed ? ` · ${card.observed}` : ""}
                  </div>
                ) : null}
                {card.ref ? (
                  <details className="mt-1">
                    <summary className="cursor-pointer text-[11.5px]" style={{ color: "var(--text-muted)" }}>
                      Details
                    </summary>
                    <span className="mono">{card.ref}</span>
                  </details>
                ) : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section data-testid="objects">
        <div className="section-label mb-1.5">Object relationships</div>
        <div className="rounded border p-3" style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }} data-testid="relationship-map">
          <BundleGraph bundle={bundle} onOpen={onOpenObject} />
        </div>
      </section>

      <div className="grid grid-cols-2 gap-5 max-[900px]:grid-cols-1">
        <Section title="Facts" testId="facts" tone="inset">
          {bundle.facts && Object.keys(bundle.facts).length ? (
            <>
              {Object.entries(bundle.facts).map(([k, v]) => {
                if (k === "sku") return null;
                if (k === "listing_as_of" && v && typeof v === "object") {
                  const covered = (v as { covered?: boolean }).covered;
                  return <Field key={k} label="listing as-of" value={covered ? "covered" : "not covered"} />;
                }
                if (v != null && typeof v === "object") return null;
                return <Field key={k} label={humanLabel(k)} value={v} />;
              })}
            </>
          ) : (
            <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
              None.
            </p>
          )}
        </Section>
        <Section title="Metrics" testId="metrics" tone="inset">
          {bundle.metrics && Object.keys(bundle.metrics).length ? (
            <>
              {Object.entries(bundle.metrics)
                .filter(([k]) => !cards.some((c) => c.label === humanLabel(k)))
                .map(([k, v]) => (
                  <Field key={k} label={humanLabel(k)} value={fmtMetric(k, v)} />
                ))}
              {!Object.entries(bundle.metrics).filter(
                ([k]) => !cards.some((c) => c.label === humanLabel(k)),
              ).length ? (
                <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                  All metrics are shown as decisive evidence above.
                </p>
              ) : null}
            </>
          ) : (
            <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
              None.
            </p>
          )}
        </Section>
        <Section title="History" testId="history" tone="inset">
          {bundle.events?.length ? (
            bundle.events.slice(0, 8).map((e, i) => (
              <div key={i} className="flex items-baseline gap-2 py-0.5 text-[13px]">
                <span className="tabular w-16 shrink-0" style={{ color: "var(--text-muted)" }}>
                  {observedDate(e.at) || "—"}
                </span>
                <span style={{ color: "var(--text-secondary)" }}>{humanLabel(e.type)}</span>
              </div>
            ))
          ) : (
            <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
              None.
            </p>
          )}
        </Section>
        <Section title="Rules & policies" testId="rules" tone="inset">
          {bundle.applicable_rules?.length ? (
            bundle.applicable_rules.map((r, i) => (
              <p key={i} className="py-0.5 text-[13.5px]">
                <span className="font-medium" style={{ color: "var(--text-primary)" }}>
                  {humanLabel(String(r.name || "rule"))}
                </span>
                {r.definition ? ` — ${String(r.definition)}` : ""}
              </p>
            ))
          ) : (
            <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
              None.
            </p>
          )}
          <div data-testid="policies" className="mt-1.5">
            {((answer?.policies || bundle.applicable_policies) || []).map((p) => (
              <p key={`${p.id}:${p.version}`} className="text-[12.5px]" style={{ color: "var(--text-muted)" }}>
                {p.title || humanLabel(p.id)}
              </p>
            ))}
          </div>
        </Section>
        <Section title="Notes" testId="evidence" tone="inset">
          {bundle.retrieved_evidence?.length ? (
            bundle.retrieved_evidence.map((ev) => (
              <p key={String(ev.note_id || ev.title)} className="py-0.5 text-[13.5px]">
                <span className="font-medium" style={{ color: "var(--text-primary)" }}>
                  {String(ev.title || ev.kind)}
                </span>
                {ev.excerpt ? ` — ${String(ev.excerpt)}` : ` — ${String(ev.body || "")}`}
              </p>
            ))
          ) : (
            <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
              None for this question.
            </p>
          )}
        </Section>
      </div>

      <details className="rounded border px-3 py-2.5" data-testid="provenance" style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}>
        <summary className="cursor-pointer text-[13px]" style={{ color: "var(--text-muted)" }}>
          Details — provenance, required evidence, tool trace, raw bundle
        </summary>
        <div className="mt-2 space-y-3">
          {!!bundle.requirements?.length ? (
            <div data-testid="requirements">
              <div className="section-label mb-1">Required evidence</div>
              <ul className="m-0 list-disc pl-5 text-[12.5px]">
                {bundle.requirements.map((r) => (
                  <li key={r.concept} style={{ color: r.present ? "var(--success)" : "var(--danger)" }}>
                    {humanLabel(r.concept)} {r.present ? "found" : "missing"}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <Field label="source" value={(bundle.provenance as Record<string, unknown>)?.tool as string} />
          <Field label="domain" value={String((bundle.provenance as Record<string, unknown>)?.domain || "resale")} />
          <Field
            label="as of"
            value={observed || String((bundle.provenance as Record<string, unknown>)?.as_of || bundle.as_of)}
          />
          <Field
            label="services"
            value={((bundle.provenance as Record<string, unknown>)?.source_tools as string[] | undefined)?.join(", ") || "—"}
          />
          {!!answer?.tool_trace?.length ? (
            <div data-testid="tool-trace">
              <div className="section-label mb-1">Tool trace</div>
              <ul className="m-0 list-disc pl-5 text-[12.5px]" style={{ color: "var(--text-secondary)" }}>
                {answer.tool_trace.map((step, i) => (
                  <li key={i}>{step.summary}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <RawBundle bundle={bundle} />
        </div>
      </details>
    </div>
  );
}

function RawBundle({ bundle }: { bundle: ContextBundle }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        className="text-[12.5px] underline focus-ring"
        style={{ color: "var(--text-muted)" }}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "Hide raw ContextBundle" : "Raw ContextBundle"}
      </button>
      {open ? <pre className="mono mt-1.5 max-h-80 overflow-auto">{JSON.stringify(bundle, null, 2)}</pre> : null}
    </div>
  );
}

function fmtMetric(key: string, value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "number") {
    if (/rate/i.test(key) && value > 0 && value < 1) return `${(value * 100).toFixed(1)}%`;
    if (/age|days/i.test(key)) return `${value} days`;
    if (/cny/i.test(key)) return `${Number(value).toLocaleString()} CNY`;
    if (/usd|price|cost/i.test(key)) return `$${Number(value).toLocaleString()}`;
    return String(value);
  }
  if (typeof value === "object") return "—";
  return String(value);
}

/* ── deterministic relationship tree (not force-directed) ── */

function BundleGraph({
  bundle,
  onOpen,
}: {
  bundle: ContextBundle;
  onOpen: (o: ContextObject) => void;
}) {
  const rels = bundle.relationships || [];
  const objects = bundle.objects || [];
  if (!rels.length && !objects.length) {
    return (
      <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
        No related objects assembled.
      </p>
    );
  }
  const children = new Map<string, Array<{ verb: string; to: string }>>();
  const targets = new Set<string>();
  for (const r of rels) {
    const list = children.get(r.from_ref) || [];
    list.push({ verb: relVerb(r.type), to: r.to_ref });
    children.set(r.from_ref, list);
    targets.add(r.to_ref);
  }
  const itemRefs = objects.filter((o) => o.type === "Item").map((o) => `${o.type}:${o.id}`);
  const roots = itemRefs.length
    ? itemRefs
    : objects.map((o) => `${o.type}:${o.id}`).filter((key) => !targets.has(key));
  const shown = roots.length ? roots : objects.map((o) => `${o.type}:${o.id}`);

  function Node({ objectKey, depth }: { objectKey: string; depth: number }) {
    const [type, id] = splitRef(objectKey);
    const obj = objects.find((o) => o.type === type && String(o.id) === id);
    const kids = children.get(objectKey) || [];
    return (
      <div>
        <button
          type="button"
          className="flex items-center gap-1.5 rounded border px-2 py-1 text-left text-[13px] focus-ring"
          style={{ background: "var(--surface-2)", borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}
          data-testid={`rel-node-${type}-${id}`}
          onClick={() => obj && onOpen(obj)}
        >
          <span className="text-[10.5px] uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
            {typeLabel(type)}
          </span>
          {obj ? (
            <span>
              {obj.type === "Item"
                ? String(obj.properties?.product || obj.id)
                : obj.type === "Listing"
                  ? `${title(obj.properties?.platform)} listing`
                  : obj.type === "EngagementObservation"
                    ? "Engagement rollup"
                    : title(obj.properties?.platform || obj.id)}
            </span>
          ) : (
            <span>{id || type}</span>
          )}
        </button>
        {kids.length > 0 && depth < 4 ? (
          <div className="ml-3 flex flex-col gap-1 border-l pl-3" style={{ borderColor: "#164e63" }}>
            {kids.map((k, i) => (
              <div key={`${objectKey}-${k.to}-${i}`}>
                <div className="mt-0.5 text-[11px]" style={{ color: "var(--accent-link)" }}>
                  {k.verb}
                </div>
                <Node objectKey={k.to} depth={depth + 1} />
              </div>
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      {shown.map((key) => (
        <Node key={key} objectKey={key} depth={0} />
      ))}
    </div>
  );
}

function title(v: unknown): string {
  const s = String(v || "").trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "—";
}

function splitRef(ref: string): [string, string] {
  const i = ref.indexOf(":");
  return i === -1 ? [ref, ""] : [ref.slice(0, i), ref.slice(i + 1)];
}
