import { useState } from "react";
import { Link, useSearch, useNavigate } from "@tanstack/react-router";
import { ChevronRight, Search } from "lucide-react";
import { LoadingDots, ErrorNote } from "@/App";
import { StatusChip } from "@/components/primitives";
import { formatMoney } from "@/lib/format";
import { useInventory } from "@/lib/api";

const FILTERS = [
  { id: "", label: "all" },
  { id: "owned", label: "owned" },
  { id: "listed", label: "listed" },
  { id: "sold", label: "sold" },
];

export function InventoryPage() {
  const search = useSearch({ strict: false }) as { status?: string; q?: string };
  const nav = useNavigate();
  const status = search.status ?? "";
  const [q, setQ] = useState(search.q ?? "");
  const inventory = useInventory(status || undefined);

  const visible = q.trim()
    ? (inventory.data || []).filter((row) =>
        `${row.product || ""} ${row.sku} ${row.status} ${row.size || ""}`
          .toLowerCase()
          .includes(q.trim().toLowerCase()),
      )
    : inventory.data || [];

  function setStatus(next: string) {
    void nav({
      to: "/inventory",
      search: next ? { status: next } : {},
    });
  }

  return (
    <div className="mx-auto max-w-6xl px-5 py-4" data-testid="inventory-page">
      <header className="mb-3 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-[17px] font-semibold tracking-tight">Inventory</h1>
          <p className="mt-0.5 text-[13px]" style={{ color: "var(--text-muted)" }}>
            {inventory.data ? `${inventory.data.length} items` : ""}
            {q.trim() && inventory.data ? ` · ${visible.length} matching` : ""}
          </p>
        </div>
        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: "var(--text-muted)" }} />
          <input
            data-testid="inventory-search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search product, size, or identifier"
            className="w-72 rounded border py-1.5 pl-8 pr-2 text-[13.5px] focus-ring"
            style={{ background: "var(--surface-1)", borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}
          />
        </div>
      </header>

      <div className="mb-2 flex gap-1">
        {FILTERS.map((f) => {
          const active = status === f.id;
          return (
            <button
              key={f.label}
              onClick={() => setStatus(f.id)}
              className={
                "rounded border px-2.5 py-1 text-[12.5px] focus-ring " + (active ? "font-medium" : "")
              }
              style={
                active
                  ? {
                      background: "var(--surface-selected)",
                      borderColor: "var(--border-strong)",
                      color: "var(--text-primary)",
                    }
                  : { borderColor: "var(--border-subtle)", color: "var(--text-muted)" }
              }
              data-testid={`inv-filter-${f.label}`}
            >
              {f.label}
            </button>
          );
        })}
      </div>

      {inventory.isError ? (
        <ErrorNote error={inventory.error} retry={() => void inventory.refetch()} />
      ) : inventory.isPending ? (
        <LoadingDots label="Loading inventory…" />
      ) : (
        <div data-testid="inventory-table">
          {visible.map((row) => (
            <Link
              key={row.sku}
              to="/inventory/$sku"
              params={{ sku: row.sku }}
              search={{ status: status || undefined }}
              data-testid={`inv-row-${row.sku}`}
              className="group grid grid-cols-[minmax(0,2fr)_100px_110px_110px_16px] items-center gap-3 border-b px-1 py-2 first:border-t focus-ring"
              style={{ borderColor: "var(--border-subtle)" }}
            >
              <div className="min-w-0">
                <span className="truncate text-[14px]" style={{ color: "var(--text-primary)" }}>
                  {row.product || row.sku}
                </span>
                {row.size ? (
                  <span className="ml-1.5 text-[12.5px]" style={{ color: "var(--text-muted)" }}>
                    {row.size}
                  </span>
                ) : null}
              </div>
              <div>
                <StatusChip tone={row.status === "sold" ? "ok" : row.status === "listed" ? "warn" : "muted"}>
                  {row.status}
                </StatusChip>
              </div>
              <div className="tabular text-[13px]" style={{ color: "var(--text-secondary)" }}>
                {formatMoney(row.acquisition_cost_cny, "CNY")}
              </div>
              <div className="tabular text-[13px]" style={{ color: "var(--text-muted)" }}>
                {row.target_price_usd != null ? formatMoney(row.target_price_usd, "USD") : "—"}
              </div>
              <ChevronRight size={14} className="opacity-0 transition-opacity group-hover:opacity-60" style={{ color: "var(--text-secondary)" }} />
            </Link>
          ))}
          {!visible.length ? (
            <p className="py-8 text-center text-[13.5px]" style={{ color: "var(--text-muted)" }}>
              {q.trim() ? "No items match the search." : "No items in this state."}
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}
