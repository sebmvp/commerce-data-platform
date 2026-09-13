import { useMemo, useState } from "react";
import type { InventoryRow } from "./types";
import { formatMoney } from "./format";
import { StatusChip } from "./ui";

export function InventoryPage({
  inventory,
  invFilter,
  setFilter,
  selectedSku,
  onOpen,
}: {
  inventory: InventoryRow[];
  invFilter: string;
  setFilter: (v: string) => void;
  selectedSku?: string;
  onOpen: (sku: string) => void;
}) {
  const [search, setSearch] = useState("");
  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return inventory;
    return inventory.filter((row) =>
      `${row.product || ""} ${row.sku} ${row.status} ${row.size || ""}`.toLowerCase().includes(q),
    );
  }, [inventory, search]);

  return (
    <div data-testid="inventory-page">
      <form className="ask" onSubmit={(e) => e.preventDefault()}>
        <input
          data-testid="inventory-search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search product, size, or identifier"
        />
      </form>
      <div className="samples">
        {[
          { id: "", label: "all" },
          { id: "owned", label: "owned" },
          { id: "listed", label: "listed" },
          { id: "sold", label: "sold" },
        ].map((st) => (
          <button
            key={st.label}
            className={`chip ${invFilter === st.id ? "active" : ""}`}
            onClick={() => setFilter(st.id)}
          >
            {st.label}
          </button>
        ))}
      </div>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Item</th>
              <th>State</th>
              <th>Listed</th>
              <th>Acquisition</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr
                key={row.sku}
                className={selectedSku === row.sku ? "selected" : ""}
                data-testid={`inv-row-${row.sku}`}
                onClick={() => onOpen(row.sku)}
              >
                <td>
                  <strong>{row.product || "Item"}</strong>
                  {row.size ? <span className="dim"> · {row.size}</span> : null}
                </td>
                <td>
                  <StatusChip tone={row.status === "sold" ? "ok" : row.status === "listed" ? "warn" : "muted"}>
                    {row.status}
                  </StatusChip>
                </td>
                <td>{row.has_active_listing ? "active" : "—"}</td>
                <td>{row.acquisition_cost_cny != null ? formatMoney(row.acquisition_cost_cny, "CNY") : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!visible.length ? <p className="empty" style={{ marginTop: 12 }}>No items match.</p> : null}
      {/* Power-user / e2e: exact identifier open */}
      <form
        className="ask power-open"
        onSubmit={(e) => {
          e.preventDefault();
          const q = search.trim();
          if (q) onOpen(q);
        }}
      >
        <input
          data-testid="sku-input"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Open by identifier"
        />
        <button type="submit">Load</button>
      </form>
    </div>
  );
}
