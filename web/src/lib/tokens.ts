export const tokens = {
  canvas: "var(--canvas)",
  surface1: "var(--surface-1)",
  surface2: "var(--surface-2)",
  selected: "var(--surface-selected)",
  borderSubtle: "var(--border-subtle)",
  borderStrong: "var(--border-strong)",
  textPrimary: "var(--text-primary)",
  textSecondary: "var(--text-secondary)",
  textMuted: "var(--text-muted)",
  accent: "var(--accent-primary)",
  accentSupport: "var(--accent-support)",
  accentFaint: "var(--accent-faint)",
  accentLink: "var(--accent-link)",
  success: "var(--success)",
  warning: "var(--warning)",
  danger: "var(--danger)",
} as const;

export type TokenName = keyof typeof tokens;
