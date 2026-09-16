/**
 * Global Business Search — deterministic, navigational. NOT the Librarian.
 * Radix Dialog palette over GET /search. ⌘K opens; Esc closes; Enter opens
 * the first hit; each hit offers Open object and Ask Librarian.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useNavigate } from "@tanstack/react-router";
import { ArrowRight, CornerDownLeft, Package, Receipt, ScrollText, Search, Sparkles, Tag } from "lucide-react";
import { useSearchResults } from "@/lib/api";
import type { SearchHit } from "@/types";

const KIND_ICON: Record<string, typeof Package> = {
  Item: Package,
  Listing: Tag,
  Order: Receipt,
  Note: ScrollText,
};

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const results = useSearchResults(query);

  // ⌘K / Ctrl+K opens, "/" focuses-opens when not already typing in an input.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) {
      setQuery("");
      // let the dialog mount before focusing
      window.setTimeout(() => inputRef.current?.focus(), 10);
    }
  }, [open]);

  const groups = useMemo(
    () =>
      (results.data?.groups || []).filter((g) => g.hits.length > 0).slice(0, 4),
    [results.data],
  );
  const firstHit = groups[0]?.hits[0];
  const searching = query.trim().length >= 2 && results.isFetching && !results.data;

  function openObject(hit: SearchHit) {
    const sku = hit.sku || hit.id;
    setOpen(false);
    void navigate({ to: "/inventory/$sku", params: { sku } });
  }

  function askLibrarian(sku: string) {
    setOpen(false);
    void navigate({
      to: "/librarian/$sku",
      params: { sku },
      search: {},
    });
  }

  return (
    <>
      <button
        type="button"
        data-testid="search-trigger"
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 rounded border px-2.5 py-1.5 text-[12.5px] focus-ring"
        style={{
          background: "var(--surface-1)",
          borderColor: "var(--border-subtle)",
          color: "var(--text-muted)",
        }}
      >
        <Search size={13} />
        Search business
        <kbd className="ml-3 rounded px-1 text-[11px]" style={{ background: "var(--surface-2)", border: "1px solid var(--border-subtle)" }}>⌘K</kbd>
      </button>

      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Overlay
            className="fixed inset-0 z-40"
            style={{ background: "rgba(6,4,12,0.62)", backdropFilter: "blur(2px)" }}
          />
          <Dialog.Content
            data-testid="command-palette"
            onKeyDown={(e: React.KeyboardEvent) => {
              if (e.key === "Enter" && firstHit && query.trim()) {
                e.preventDefault();
                openObject(firstHit);
              }
            }}
            className="fixed left-1/2 top-[14vh] z-50 w-[min(620px,92vw)] -translate-x-1/2 rounded border focus-ring"
            style={{
              background: "var(--canvas)",
              borderColor: "var(--border-strong)",
              boxShadow: "0 18px 60px rgba(0,0,0,.55)",
            }}
          >
            <Dialog.Title className="sr-only">Search business</Dialog.Title>

            <div
              className="flex items-center gap-2 border-b px-3.5 py-3"
              style={{ borderColor: "var(--border-subtle)" }}
            >
              <Search size={15} style={{ color: "var(--text-muted)" }} />
              <input
                ref={inputRef}
                data-testid="palette-input"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search items, listings, orders, notes"
                className="flex-1 bg-transparent text-[14.5px] outline-none"
                style={{ color: "var(--text-primary)" }}
              />
              <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>esc</span>
            </div>

            <div className="max-h-[54vh] overflow-y-auto px-1.5 py-2">
              {searching ? (
                <p className="px-2 py-3 text-[13px]" style={{ color: "var(--text-muted)" }}>
                  Searching…
                </p>
              ) : null}
              {!query.trim() ? (
                <p className="px-2 py-3 text-[13px]" style={{ color: "var(--text-muted)" }}>
                  Find a product, listing, order, or note. This is search, not
                  the Librarian — it does not assemble context.
                </p>
              ) : null}
              {query.trim().length >= 2 && !searching && !groups.length && !results.isError ? (
                <p className="px-2 py-3 text-[13px]" style={{ color: "var(--text-muted)" }}>
                  No matching objects.
                </p>
              ) : null}
              {results.isError ? (
                <p className="px-2 py-3 text-[13px]" style={{ color: "var(--danger)" }}>
                  Search failed. {results.error instanceof Error ? results.error.message : ""}
                </p>
              ) : null}

              {groups.map((g) => {
                const Icon = KIND_ICON[g.type] || Package;
                return (
                  <div key={g.type} className="mb-2">
                    <div className="section-label px-2 py-1">{g.type}s</div>
                    {g.hits.slice(0, 6).map((hit) => {
                      const sku = hit.sku || hit.id;
                      return (
                        <div
                          key={`${g.type}-${hit.id}`}
                          data-testid={`search-hit-${g.type.toLowerCase()}`}
                          role="button"
                          tabIndex={0}
                          onClick={() => openObject(hit)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") openObject(hit);
                          }}
                          className="group flex cursor-pointer items-center gap-2.5 rounded px-2 py-1.5 focus-ring"
                          style={{ border: "1px solid transparent" }}
                          onMouseEnter={(e) => {
                            (e.currentTarget as HTMLDivElement).style.background = "var(--surface-1)";
                          }}
                          onMouseLeave={(e) => {
                            (e.currentTarget as HTMLDivElement).style.background = "transparent";
                          }}
                        >
                          <Icon size={14} style={{ color: "var(--text-muted)", flexShrink: 0 }} />
                          <span
                            className="min-w-0 flex-1 truncate text-[13.5px]"
                            style={{ color: "var(--text-primary)" }}
                          >
                            {hit.label}
                          </span>
                          <span
                            className="tabular shrink-0 text-[12px]"
                            style={{ color: "var(--text-muted)" }}
                          >
                            {hit.meta}
                          </span>
                          <button
                            type="button"
                            className="flex shrink-0 items-center gap-1 rounded border px-1.5 py-0.5 text-[11.5px] focus-ring md:hidden xl:flex"
                            style={{ borderColor: "var(--accent-link)", color: "var(--accent-link)" }}
                            onClick={(e) => {
                              e.stopPropagation();
                              askLibrarian(sku);
                            }}
                          >
                            <Sparkles size={11} /> Ask Librarian
                          </button>
                          <ArrowRight
                            size={13}
                            className="shrink-0 opacity-0 transition-opacity group-hover:opacity-60"
                            style={{ color: "var(--text-muted)" }}
                          />
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>

            {query.trim() && firstHit ? (
              <div
                className="flex items-center gap-3 border-t px-3.5 py-2 text-[11.5px]"
                style={{ borderColor: "var(--border-subtle)", color: "var(--text-muted)" }}
              >
                <span className="flex items-center gap-1">
                  <CornerDownLeft size={11} /> open first result
                </span>
                <span className="flex items-center gap-1">
                  <Sparkles size={11} /> ask the Librarian from a hit
                </span>
              </div>
            ) : null}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
