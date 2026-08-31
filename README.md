# Commerce Data Platform

[![test](https://github.com/sebmvp/commerce-data-platform/actions/workflows/test.yml/badge.svg)](https://github.com/sebmvp/commerce-data-platform/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab)](https://www.python.org/)
[![DuckDB](https://img.shields.io/badge/warehouse-DuckDB-yellow)](https://duckdb.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> **One-liner:** turns messy multi-source operational data into a **reproducible,
> validated, auditable** analytical store — one `docker compose up` away.

A working reference implementation of the ingest-and-analytics problems a small
resale operation actually has: sourcing manifests live in one file, marketplace
listings in another, shipment status in a spreadsheet, and engagement in
screenshots. Consolidating them into **one analytical warehouse** means pricing,
inventory, and content decisions stop being gut calls.

**Engineering properties this demonstrates** (the interesting bits):

- **8 ingestion streams**, each independently idempotent (content-hash skip +
  natural-key upsert) — re-running `cdp build` is provably a no-op
- **Schema validation pre-insert** — pydantic per stream; rejects quarantined
  to `core.rejected_records` with reasons, never silent
- **SCD-2 dimensions** — point-in-time queries work against fee/standing history
- **Event-sourced supply chain** — item state is a projection over an
  append-only `item_events` stream
- **Audit trail of every run** — `core.ingest_runs` records read/loaded/rejected
  counts, duration, and content-hash for change detection
- **End-to-end CI** — pytest + a fresh `cdp build --sample` smoke on every push

```
           canonical JSONL sources                     warehouse.duckdb (cache)
    sourcing manifests · marketplace CSVs                 core   audit + dims
    shipment trackers  · engagement logs   ──►  ►►►►   catalog items + events
    content Pieces     · order exports         validate   supply purchase orders
                          8 streams          quarantine   sales  listings/orders
                                                 upsert   insights voice + funnels
                        │                                │
                        └──── audit (ingest_runs) ───────►
                        └──── rejects (rejected_records) ─►
                        │
                        ▼
                   CLI (`cdp build` · `cdp report` · `cdp query`)
                       │
                       ├─► FastAPI read layer  (/inventory, /listings, /sell-through)
                       └─► Markdown exports     (weekly ops briefs)
```

---

## Quick start — one command, no config

```bash
git clone https://github.com/sebmvp/commerce-data-platform && cd commerce-data-platform
docker compose up build          # builds the warehouse from synthetic sample data
docker compose up api            # FastAPI read layer at http://localhost:8000/docs
```

Or without Docker:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,api]"
cdp build --sample               # validate + ingest warehouse from sample_data/
cdp status                       # health check: tables, row counts, rejects
cdp report funnel                # -> markdown analytics export
cdp serve                        # optional FastAPI read layer
```

Actual output of `cdp status` on the bundled synthetic dataset:

```
db: /path/to/commerce-data-platform/warehouse.duckdb (6.3 MB)
  items              12
  item_events        39
  listings           9
  orders             6
  engagement_snaps   71
  content_pieces     9
  voice_profiles     1
  rejected_records   0
  ingest_runs        8
```

Actual `cdp report funnel` (first table — markdown export):

```
| platform | listings | sold | sell_through | avg_days_to_sell | gross_usd |
| -------- | -------- | ---- | ------------ | ---------------- | --------- |
| grailed  | 8        | 5    | 0.62         | 7.2              | $2,765.32 |
| depop    | 1        | 1    | 1.00         | 17.0             | $388.51   |
```

The dataset in `sample_data/` is intentionally small — it's a **demo
fixture**, not a scale claim. See [docs/assumptions.md](docs/assumptions.md)
for the distribution reasoning; the generator script itself is committed
and deterministic.

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
