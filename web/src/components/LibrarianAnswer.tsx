import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { Field } from "@/components/primitives";
import {
  decisiveCards,
  humanLabel,
  observedDate,
  relVerb,
  whyText,
  typeLabel,
  channelName,
} from "@/lib/format";
import type { ContextBundle, ContextObject, LibrarianResponse } from "@/types";

/**
 * Librarian answer surfaces, three levels:
 *   1 — decision (answer, sufficiency, why, proposed action, missing context)
 *   2 — business context (decisive evidence, relationships, facts/history/rules)
 *   3 — technical (provenance, refs, tool trace, raw bundle) behind <details>
 * Shared by the full workspace and the contextual object panel.
 */
export function LibrarianAnswer({
  answer,
  bundle,
  objects,
  compact,
  onOpenObject,
}: {
  answer: LibrarianResponse | null;
  bundle: ContextBundle;
  objects: ContextObject[];
  compact?: boolean;
  onOpenObject?: (o: ContextObject) => void;
}) {
  const sufficient = bundle.sufficient;
  const cards = decisiveCards(answer, bundle);
  const inactive = answer?.grounding_status === "invalid";
  const abstained = answer?.abstained || answer?.grounding_status === "abstained";
  const fake =
    (answer?.provider === "fake" || answer?.provider_kind === "fake") &&
    (answer?.answer || "").includes("fake provider");
  const showAnswerText = !abstained && answer && answer.answer;

  return (
    <div className="space-y-4">
      {/* Level 1 — decision. The only heavy surface. */}
      <section
        className="rounded border p-4"
        data-testid="sufficiency"
        style={{
          background: "var(--surface-1)",
          borderColor: sufficient ? "#14532d" : "#7f1d1d",
        }}
      >
        {!abstained && showAnswerText ? (
          <>
            <div className="flex items-baseline gap-2">
              <StatusLike tone={sufficient ? "ok" : "bad"}>
                {sufficient ? "SUFFICIENT" : "INSUFFICIENT"}
              </StatusLike>
              {inactive ? (
                <span className="text-[12px]" style={{ color: "var(--danger)" }}>
                  grounding rejected the model output
                </span>
              ) : null}
            </div>
            <p
              className="mt-1.5 max-w-[68ch] text-[14.5px]"
              style={{ color: "var(--text-primary)" }}
              data-testid="answer-text"
            >
              {answer!.answer}
            </p>
            {fake || answer?.provider_kind === "fake" ? (
              <p className="mt-1 text-[12px]" style={{ color: "var(--text-muted)" }}>
                Test provider — extractive restatement, not model reasoning.
              </p>
            ) : null}
            {!!answer!.caveats?.length ? (
              <p className="mt-1 text-[12.5px]" style={{ color: "var(--text-muted)" }}>
                {answer!.caveats.join(" · ")}
              </p>
            ) : null}
          </>
        ) : (
          <div>
            <StatusLike tone={sufficient ? "ok" : "bad"}>
              {sufficient ? "SUFFICIENT" : "INSUFFICIENT"}
            </StatusLike>
            <p className="mt-1.5 text-[14.5px]" style={{ color: "var(--text-secondary)" }} data-testid="answer-text">
              {inactive
                ? "Grounding rejected the model output."
                : "Context is not sufficient to answer — see what is missing below."}
            </p>
          </div>
        )}

        <div className="mt-3 border-t pt-3" style={{ borderColor: "var(--border-subtle)" }}>
          <div className="section-label mb-1">Why</div>
          <p
            className="max-w-[70ch] text-[13.5px]"
            style={{ color: "var(--text-secondary)" }}
            data-testid="why"
          >
            {whyText(bundle.why)}
          </p>
        </div>

        {!!answer?.suggested_action ? (
          <p
            className="mt-2 text-[13px]"
            data-testid="suggested-action"
            style={{ color: "var(--accent-support)" }}
          >
            Proposed sandbox action: {humanLabel(answer.suggested_action.action_type)}
            {answer.suggested_action.recommendation
              ? ` · ${humanLabel(String(answer.suggested_action.recommendation))}`
              : ""}{" "}
            (human approval required)
          </p>
        ) : null}

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
              {objects.some((o) => o.type === "Item") ? (
                <Link
                  to="/inventory/$sku"
                  params={{ sku: String(objects.find((o) => o.type === "Item")!.id) }}
                  className="text-[12px] focus-ring underline-offset-2 hover:underline"
                  style={{ color: "var(--accent-link)" }}
                >
                  Inspect this object
                </Link>
              ) : null}
            </div>
            <ul className="m-0 list-disc pl-5 text-[13px]" style={{ color: "var(--text-secondary)" }}>
              {bundle.missing_context.map((m) => (
                <li key={m.concept}>
                  <span style={{ color: "var(--text-primary)" }}>{humanLabel(m.concept)}</span> —{" "}
                  {whyText(m.reason)}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      {/* Level 2 — business context */}
      {cards.length ? (
        <section data-testid="cited-evidence">
          <div className="section-label mb-1.5">Decisive evidence</div>
          <div
            className={
              compact
                ? "space-y-1.5"
                : "grid grid-cols-[repeat(auto-fill,minmax(170px,1fr))] gap-2"
            }
          >
            {cards.map((card) => (
              <div
                key={card.label}
                className="rounded border px-2.5 py-2"
                style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}
              >
                <div className="section-label">{card.label}</div>
                <div
                  className="tabular mt-0.5 font-semibold tracking-tight"
                  style={{
                    fontSize: compact ? "14.5px" : "17px",
                    color: "var(--text-primary)",
                  }}
                >
                  {card.value}
                </div>
                {card.source ? (
                  <div className="mt-0.5 text-[12px]" style={{ color: "var(--text-muted)" }}>
                    {card.source}
                    {card.observed ? ` · observed ${card.observed}` : ""}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section data-testid="objects">
        <div className="section-label mb-1.5">Object relationships</div>
        <div
          className="rounded border p-3"
          style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}
          data-testid="relationship-map"
        >
          <BundleGraph bundle={bundle} objects={objects} onOpen={onOpenObject} />
        </div>
      </section>

      {!compact ? (
        <div className="grid grid-cols-2 gap-5 max-[900px]:grid-cols-1">
          <BundleFacts bundle={bundle} />
        </div>
      ) : null}

      {/* Level 3 — technical evidence. Never in the first viewport. */}
      <details
        className="rounded border px-3 py-2.5"
        data-testid="provenance"
        style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}
      >
        <summary className="cursor-pointer text-[12.5px]" style={{ color: "var(--text-muted)" }}>
          Details — provenance, required evidence, tool trace, raw bundle
        </summary>
        <div className="mt-2 space-y-3">
          <BundleTechnical bundle={bundle} answer={answer} />
        </div>
      </details>
    </div>
  );
}

/* Small local chip so the answer component carries no page-level imports */
function StatusLike({
  tone,
  children,
}: {
  tone: "ok" | "bad";
  children: React.ReactNode;
}) {
  const color = tone === "ok" ? "var(--success)" : "var(--danger)";
  const border = tone === "ok" ? "#14532d" : "#7f1d1d";
  return (
    <span
      className="inline-flex items-center rounded-sm border px-1.5 py-0.5 text-[12px] font-semibold"
      style={{ color, border, borderColor: border }}
      data-testid="sufficiency-chip"
    >
      {children}
    </span>
  );
}

function BundleFacts({
  bundle,
}: {
  bundle: ContextBundle;
}) {
  const metrics = bundle.metrics || {};
  const cardLabels = decisiveEvidenceLabels(bundle);
  return (
    <>
      <section data-testid="facts" className="rounded border p-3" style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}>
        <div className="section-label mb-1.5">Facts</div>
        {bundle.facts && Object.keys(bundle.facts).length ? (
          Object.entries(bundle.facts).map(([k, v]) => {
            if (k === "sku") return null;
            if (k === "listing_as_of" && v && typeof v === "object") {
              const covered = (v as { covered?: boolean }).covered;
              return <Field key={k} label="listing as-of" value={covered ? "covered" : "not covered"} />;
            }
            if (v != null && typeof v === "object") return null;
            return <Field key={k} label={humanLabel(k)} value={v} />;
          })
        ) : (
          <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
            No facts assembled.
          </p>
        )}
      </section>
      <section data-testid="metrics" className="rounded border p-3" style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}>
        <div className="section-label mb-1.5">Metrics</div>
        {Object.keys(metrics).length ? (
          Object.entries(metrics)
            .filter(([k]) => !cardLabels.has(humanLabel(k).toLowerCase()))
            .map(([k, v]) => <Field key={k} label={humanLabel(k)} value={fmtMetric(k, v)} />)
        ) : (
          <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
            All metrics are shown as decisive evidence above.
          </p>
        )}
      </section>
      <section data-testid="history" className="rounded border p-3" style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}>
        <div className="section-label mb-1.5">History</div>
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
            No events in this bundle.
          </p>
        )}
      </section>
      <section data-testid="rules" className="rounded border p-3" style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}>
        <div className="section-label mb-1.5">Applicable guidance</div>
        {bundle.applicable_rules?.length ? (
          bundle.applicable_rules
            .filter((r) => (r as Record<string, unknown>).implemented !== false)
            .map((r, i) => (
              <p key={i} className="py-0.5 text-[13.5px]">
                <span className="font-medium" style={{ color: "var(--text-primary)" }}>
                  {humanLabel(String((r as Record<string, unknown>).name || "rule"))}
                </span>
                {(r as Record<string, unknown>).definition
                  ? ` — ${String((r as Record<string, unknown>).definition)}`
                  : ""}
              </p>
            ))
        ) : (
          <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
            No rules assembled.
          </p>
        )}
        <div data-testid="policies" className="mt-1.5">
          {((bundle.applicable_policies || []) as unknown as Array<Record<string, unknown>>).map((p) => (
            <p key={String(p.id)} className="text-[12.5px]" style={{ color: "var(--text-muted)" }}>
              {String(p.title || humanLabel(String(p.id)))}
            </p>
          ))}
        </div>
      </section>
      <section data-testid="evidence" className="rounded border p-3" style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}>
        <div className="section-label mb-1.5">Notes</div>
        {(bundle.retrieved_evidence || []).length ? (
          (bundle.retrieved_evidence || []).map((ev) => {
            const r = ev as Record<string, unknown>;
            return (
              <p key={String(r.note_id || r.title)} className="py-0.5 text-[13.5px]">
                <span className="font-medium" style={{ color: "var(--text-primary)" }}>
                  {String(r.title || r.kind)}
                </span>
                {r.excerpt ? ` — ${String(r.excerpt)}` : r.body ? ` — ${String(r.body)}` : ""}
              </p>
            );
          })
        ) : (
          <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
            No note evidence for this question.
          </p>
        )}
      </section>
    </>
  );
}

function BundleTechnical({
  bundle,
  answer,
}: {
  bundle: ContextBundle;
  answer: LibrarianResponse | null;
}) {
  return (
    <>
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
      <Field
        label="domain"
        value={String((bundle.provenance as Record<string, unknown>)?.domain || "resale")}
      />
      <Field
        label="as of"
        value={observedDate(bundle.as_of) || String((bundle.provenance as Record<string, unknown>)?.as_of || bundle.as_of)}
      />
      <Field
        label="services"
        value={
          ((bundle.provenance as Record<string, unknown>)?.source_tools as string[] | undefined)?.join(", ") ||
          "—"
        }
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
    </>
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
      {open ? (
        <pre className="mono mt-1.5 max-h-80 overflow-auto">
          {JSON.stringify(bundle, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}

/* ── deterministic relationship tree (not force-directed) ── */

function BundleGraph({
  bundle,
  objects,
  onOpen,
}: {
  bundle: ContextBundle;
  objects: ContextObject[];
  onOpen?: (o: ContextObject) => void;
}) {
  const rels = bundle.relationships || [];
  const objs = objects.length ? objects : bundle.objects || [];
  if (!rels.length && !objs.length) {
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
  const itemRefs = objs.filter((o) => o.type === "Item").map((o) => `${o.type}:${o.id}`);
  const roots = itemRefs.length
    ? itemRefs
    : objs.map((o) => `${o.type}:${o.id}`).filter((key) => !targets.has(key));
  const shown = roots.length ? roots : objs.map((o) => `${o.type}:${o.id}`);

  function Node({ objectKey, depth }: { objectKey: string; depth: number }) {
    const idx = objectKey.indexOf(":");
    const type = idx === -1 ? objectKey : objectKey.slice(0, idx);
    const id = idx === -1 ? "" : objectKey.slice(idx + 1);
    const obj = objs.find((o) => o.type === type && String(o.id) === id);
    const kids = children.get(objectKey) || [];
    return (
      <div>
        <button
          type="button"
          className="flex items-center gap-1.5 rounded border px-2 py-1 text-left text-[13px] focus-ring"
          style={{
            background: "var(--surface-2)",
            borderColor: "var(--border-subtle)",
            color: "var(--text-primary)",
          }}
          data-testid={`rel-node-${type}-${id}`}
          onClick={() => obj && onOpen?.(obj)}
        >
          <span className="text-[10.5px] uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
            {typeLabel(type)}
          </span>
          {obj ? (
            <span>
              {obj.type === "Item"
                ? String(obj.properties?.product || obj.id)
                : obj.type === "Listing"
                  ? `${channelName(obj.properties?.platform)} listing`
                  : obj.type === "EngagementObservation"
                    ? "Engagement rollup"
                    : titleCase(obj.properties?.platform || obj.id)}
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

function titleCase(v: unknown): string {
  const s = String(v || "").trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "—";
}

/* Labels already surfaced as decisive evidence; Level 2 hides the duplicates. */
function decisiveEvidenceLabels(bundle: ContextBundle): Set<string> {
  const labels = new Set<string>();
  for (const [key, value] of Object.entries(bundle.metrics || {})) {
    if (value != null) labels.add(humanLabel(key).toLowerCase());
  }
  return labels;
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
