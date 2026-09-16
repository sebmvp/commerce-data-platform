import { useMemo, useState } from "react";
import { useNavigate, useParams, useSearch } from "@tanstack/react-router";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { ChevronDown, ChevronUp, Search } from "lucide-react";
import { LoadingDots, ErrorNote } from "@/App";
import { StatusChip } from "@/components/primitives";
import { ObjectPanel } from "@/components/ObjectPanel";
import { formatMoney } from "@/lib/format";
import { useInventory } from "@/lib/api";
import type { InventoryRow } from "@/types";

const FILTERS = [
  { id: "", label: "All" },
  { id: "owned", label: "Owned" },
  { id: "listed", label: "Listed" },
  { id: "sold", label: "Sold" },
] as const;

type SearchParams = { status?: string; q?: string; sku?: string };

export function InventoryPage() {
  const search = useSearch({ strict: false }) as SearchParams;
  const navigate = useNavigate();
  const status = search.status ?? "";
  const [q, setQ] = useState(search.q ?? "");
  const [sorting, setSorting] = useState<SortingState>([]);
  const inventory = useInventory(status || undefined);
  // Path is the shareable truth: /inventory/$sku selects the object even
  // without ?sku= in the query string.
  const params = useParams({ strict: false }) as { sku?: string };
  const activeSku = params.sku || search.sku || null;

  const filtered = useMemo(() => {
    const rows = inventory.data || [];
    const needle = q.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((row) =>
      `${row.product || ""} ${row.sku} ${row.status} ${row.size || ""}`
        .toLowerCase()
        .includes(needle),
    );
  }, [inventory.data, q]);

  const columns = useMemo<ColumnDef<InventoryRow>[]>(
    () => [
      {
        accessorKey: "product",
        header: "Product",
        cell: (info) => (
          <span
            className="block truncate text-[14px]"
            style={{ color: "var(--text-primary)" }}
          >
            {String(info.getValue() || info.row.original.sku || "")}
          </span>
        ),
      },
      {
        accessorKey: "size",
        header: "Size",
        cell: (info) => (
          <span style={{ color: "var(--text-secondary)" }}>
            {String(info.getValue() || "") || "—"}
          </span>
        ),
      },
      {
        accessorKey: "status",
        header: "State",
        cell: (info) => (
          <StatusChip
            tone={
              info.getValue() === "sold"
                ? "ok"
                : info.getValue() === "listed"
                  ? "warn"
                  : "muted"
            }
          >
            {String(info.getValue() || "—")}
          </StatusChip>
        ),
      },
      {
        accessorKey: "acquisition_cost_cny",
        header: "Acquisition",
        cell: (info) => (
          <span className="tabular" style={{ color: "var(--text-secondary)" }}>
            {formatMoney(info.getValue(), "CNY")}
          </span>
        ),
      },
      {
        accessorKey: "target_price_usd",
        header: "Ask",
        cell: (info) => (
          <span className="tabular" style={{ color: "var(--text-secondary)" }}>
            {info.getValue() != null ? formatMoney(info.getValue(), "USD") : "—"}
          </span>
        ),
      },
      {
        id: "attention",
        header: "Attention",
        enableSorting: false,
        cell: (info) =>
          info.row.original.has_active_listing === false &&
          info.row.original.status === "owned" ? (
            <StatusChip tone="info">LIST</StatusChip>
          ) : null,
      },
    ],
    [],
  );

  const table = useReactTable({
    data: filtered,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  function setStatus(next: string) {
    void navigate({
      to: activeSku ? "/inventory/$sku" : "/inventory",
      params: activeSku ? { sku: activeSku } : undefined,
      search: next ? { status: next } : {},
    });
  }

  function selectRow(sku: string) {
    void navigate({
      to: "/inventory/$sku",
      params: { sku },
      search: status ? { status } : {},
    });
  }

  const anyInTransit = filtered.some(
    (r) => r.status !== "" && !FILTERS.some((f) => f.id === r.status),
  );

  return (
    <div className="flex h-full min-w-0" data-testid="inventory-page">
      {/* Left: the table always stays mounted */}
      <div className="flex min-w-0 flex-1 flex-col px-6 py-5">
        <header className="mb-3 flex items-end justify-between gap-4">
          <div>
            <h1 className="text-[18px] font-semibold tracking-tight">Inventory</h1>
            <p className="tabular mt-0.5 text-[12.5px]" style={{ color: "var(--text-muted)" }}>
              {inventory.data ? `${inventory.data.length} items` : ""}
              {q.trim() && inventory.data ? ` · ${filtered.length} matching` : ""}
            </p>
          </div>
          <div className="relative">
            <Search
              size={14}
              className="absolute left-2.5 top-1/2 -translate-y-1/2"
              style={{ color: "var(--text-muted)" }}
            />
            <input
              data-testid="inventory-search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search product, size, or identifier"
              className="w-72 rounded border py-1.5 pl-8 pr-2 text-[13.5px] focus-ring"
              style={{
                background: "var(--surface-1)",
                borderColor: "var(--border-subtle)",
                color: "var(--text-primary)",
              }}
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
                  "rounded border px-2.5 py-1 text-[12.5px] focus-ring " +
                  (active ? "font-medium" : "")
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
                data-testid={`inv-filter-${f.label.toLowerCase()}`}
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
          <div
            data-testid="inventory-table"
            className="min-w-0 flex-1 overflow-auto rounded border"
            style={{ borderColor: "var(--border-subtle)" }}
          >
            <table className="w-full border-collapse text-left">
              <thead className="sticky top-0 z-10" style={{ background: "var(--surface-2)" }}>
                {table.getHeaderGroups().map((hg) => (
                  <tr key={hg.id}>
                    {hg.headers.map((header) => (
                      <th
                        key={header.id}
                        className="border-b px-3 py-2 pr-6 text-[11.5px] font-medium uppercase tracking-wide"
                        style={{
                          borderColor: "var(--border-subtle)",
                          color: "var(--text-muted)",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {header.column.getCanSort() ? (
                          <button
                            type="button"
                            data-testid={`sort-${header.id}`}
                            onClick={header.column.getToggleSortingHandler()}
                            className="inline-flex items-center gap-1 focus-ring"
                          >
                            {flexRender(header.column.columnDef.header, header.getContext())}
                            {header.column.getIsSorted() === "asc" ? (
                              <ChevronUp size={12} />
                            ) : header.column.getIsSorted() === "desc" ? (
                              <ChevronDown size={12} />
                            ) : null}
                          </button>
                        ) : (
                          flexRender(header.column.columnDef.header, header.getContext())
                        )}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => {
                  const selected = row.original.sku === activeSku;
                  return (
                    <tr
                      key={row.id}
                      data-testid={`inv-row-${row.original.sku}`}
                      onClick={() => selectRow(row.original.sku)}
                      className="cursor-pointer border-b focus-ring"
                      style={{
                        borderColor: "var(--border-subtle)",
                        background: selected ? "var(--surface-selected)" : undefined,
                        boxShadow: selected
                          ? "inset 2px 0 0 var(--accent-primary)"
                          : undefined,
                      }}
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="px-3 py-2 pr-6 align-middle" style={{ whiteSpace: "nowrap" }}>
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  );
                })}
                {!table.getRowModel().rows.length ? (
                  <tr>
                    <td
                      colSpan={columns.length}
                      className="py-8 text-center text-[13.5px]"
                      style={{ color: "var(--text-muted)" }}
                    >
                      {q.trim() ? "No items match the search." : "No items in this state."}
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Right: object panel keeps the table mounted (wide viewport) */}
      {activeSku ? (
        <div
          data-testid="object-panel"
          className="w-[460px] shrink-0 overflow-y-auto border-l max-[1100px]:fixed max-[1100px]:inset-y-0 max-[1100px]:right-0 max-[1100px]:z-30 max-[1100px]:w-[min(460px,92vw)] max-[1100px]:shadow-2xl"
          style={{ background: "var(--canvas)", borderColor: "var(--border-subtle)" }}
        >
          <ObjectPanel sku={activeSku} status={status} />
        </div>
      ) : anyInTransit ? null : null}
    </div>
  );
}
