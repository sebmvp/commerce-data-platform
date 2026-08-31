# Commerce Data Platform

Operational data integration, validation, and analytics for a resale-commerce
operation — built around **DuckDB**, **canonical JSONL sources**, and
**reproducible, idempotent ingest**. Everything is rebuildable from source
files; the warehouse file itself is disposable.

> Personal portfolio project. All bundled data under `sample_data/` is fully
> synthetic.

## Why this exists

Running a small resale business means data lives everywhere: sourcing
spreadsheets, marketplace exports, shipment trackers, engagement screenshots.
This project consolidates those streams into **one analytical store** with a
single CLI, so questions like *"what's my sell-through by channel?"* or
*"which content tone actually converts watchers into buyers?"* are one SQL
query away — and the answer is reproducible.

Design principles:

1. **Canonical inputs preserved.** Every fact row keeps its raw source
   payload (`raw_json`) and source file. The DuckDB file can be deleted and
   rebuilt losslessly: `cdp build`.
2. **Idempotent ingest.** Every table has a natural upsert key. Re-running
   `cdp ingest` is a no-op for unchanged files (content-hash detection).
3. **Validation before insert.** Rows failing schema checks are quarantined
   into `core.rejected_records` with reasons — never silently dropped.
4. **Event sourcing for supply chain.** `catalog.item_events` is the source
   of truth; `catalog.items` is the latest projection.

## Architecture

```
sourcing files ──┐
marketplace CSV ─┼─► [validate] ─► [idempotent ingest] ─► DuckDB ─► [views] ─► reports
engagement logs ─┘      │                                    │
                        ▼                                    ▼
              core.rejected_records              FastAPI read layer (optional)
```

Schemas: `core` (dims + ingest audit), `catalog` (inventory + item events),
`supply` (purchase orders), `sales` (listings, engagement, orders),
`insights` (content performance + voice profiles + funnels).

## Quick start (5 minutes)

```bash
git clone https://github.com/sebmvp/commerce-data-platform
cd commerce-data-platform
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Build the warehouse from scratch (creates schema, views, bars sample data)
cdp build --sample

# Explore
cdp status                                  # health snapshot
cdp tables                                  # row counts per table
cdp query "SELECT * FROM sales.v_listing_performance LIMIT 10"
cdp report inventory                        # markdown summary -> reports/

# Optional API layer
pip install -e ".[api]"
cdp serve                                   # http://localhost:8000/docs
```

Or with Docker:

```bash
docker build -t cdp .
docker run --rm cdp build --sample && docker run --rm cdp status
docker compose up api       # API + warehouse volume
```

## What's inside

| Layer | Path | Role |
|-------|------|------|
| Schema | `schema/001_init.sql` | DDL — the source of truth |
| Views | `sql/views.sql` | Analytics surface (`v_*`) |
| CLI | `src/cdp_cli/cli.py` | `init / build / ingest / validate / query / report / serve` |
| Ingest | `src/cdp_cli/ingest/` | Per-source loaders, pydantic validation, run audit |
| Sample data | `sample_data/*.jsonl` | Synthetic — safe to commit |
| Tests | `tests/` | pytest, incl. ingest idempotency |
| CI | `.github/workflows/test.yml` | pytest + smoke build on every push |

## Command reference

```
cdp init                create schema + views (implicit in build)
cdp build [--sample]    full rebuild: schema, views, validate+ingest, aggregates
cdp ingest [source]     ingest one source or all (idempotent)
cdp validate            dry-run validation report, no writes
cdp query "SQL"         ad-hoc SQL against the warehouse
cdp report <kind>       inventory | pricing | funnel  -> markdown export
cdp status              db size + key row counts
cdp serve [--port N]    FastAPI read layer (optional extra)
```

## Testing & CI

```bash
pytest -q
```

GitHub Actions runs the suite plus an end-to-end smoke build on every push.

## Data dictionary

See [docs/data-dictionary.md](docs/data-dictionary.md),
[ARCHITECTURE.md](ARCHITECTURE.md), and [docs/assumptions.md](docs/assumptions.md)
for how the synthetic sample data was generated and why distribution choices
were made.
