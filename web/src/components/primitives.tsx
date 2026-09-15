import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Page regions, not cards. Cards should mark a real contained concept —
 * most separators in this app are hairlines and spacing instead.
 */
export function Section({
  title,
  children,
  testId,
  className,
  actions,
  tone,
}: {
  title?: string;
  children: React.ReactNode;
  testId?: string;
  className?: string;
  actions?: React.ReactNode;
  tone?: "inset";
}) {
  const inner = (
    <>
      {title || actions ? (
        <div className="mb-2 flex items-center justify-between gap-3">
          {title ? <h2 className="section-label">{title}</h2> : null}
          {actions}
        </div>
      ) : null}
      {children}
    </>
  );
  if (tone === "inset") {
    return (
      <section
        data-testid={testId}
        className={cn(
          "rounded border p-3",
          className,
        )}
        style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)" }}
      >
        {inner}
      </section>
    );
  }
  return (
    <section data-testid={testId} className={className}>
      {inner}
    </section>
  );
}

export function Field({
  label,
  value,
  mono,
}: {
  label: string;
  value: unknown;
  mono?: boolean;
}) {
  return (
    <div className="grid grid-cols-[110px_1fr] gap-2 py-0.5 text-[13.5px]">
      <dt className="text-[12.5px]" style={{ color: "var(--text-muted)" }}>
        {label}
      </dt>
      <dd className={cn("m-0 min-w-0", mono && "mono")} style={{ color: "var(--text-primary)" }}>
        {kvalue(value)}
      </dd>
    </div>
  );
}

function kvalue(value: unknown): string {
  if (value == null || value === "") return "—";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

const CHIP_TONES: Record<string, { fg: string; border: string }> = {
  ok: { fg: "var(--success)", border: "#14532d" },
  bad: { fg: "var(--danger)", border: "#7f1d1d" },
  warn: { fg: "var(--warning)", border: "#78350f" },
  muted: { fg: "var(--text-muted)", border: "var(--border-subtle)" },
  info: { fg: "var(--accent-link)", border: "#164e63" },
};

export function StatusChip({
  children,
  tone = "muted",
  testId,
}: {
  children: React.ReactNode;
  tone?: keyof typeof CHIP_TONES;
  testId?: string;
}) {
  const t = CHIP_TONES[tone];
  return (
    <span
      data-testid={testId}
      className="inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-[12px]"
      style={{ color: t.fg, borderColor: t.border }}
    >
      {children}
    </span>
  );
}
