import type { ReactNode } from "react";
import { kv } from "./format";

export function Section({
  title,
  children,
  testId,
  kicker,
}: {
  title: string;
  children: ReactNode;
  testId?: string;
  kicker?: string;
}) {
  return (
    <section className="card" data-testid={testId}>
      {kicker ? <div className="kicker">{kicker}</div> : null}
      <h2>{title}</h2>
      {children}
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
    <div className="field">
      <dt>{label}</dt>
      <dd className={mono ? "mono" : undefined}>{kv(value)}</dd>
    </div>
  );
}

export function StatusChip({
  children,
  tone,
}: {
  children: ReactNode;
  tone?: "ok" | "bad" | "warn" | "muted";
}) {
  return <span className={`status-chip ${tone || "muted"}`}>{children}</span>;
}
