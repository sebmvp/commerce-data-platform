# Architecture

High-level data flow and module layout.

```
     ┌──────────────────────┐
     │   Canonical sources  │  JSONL on disk / filesystem of record
     │  (Sourcing manifest, │
     │   marketplace CSVs,  │
     │   engagement logs)   │
     └────────┬─────────────┘
              │
              ▼
       ┌─────────────┐    ┌────────────────┐
       │  Validation  │───►│ Quarantine to  │   core.rejected_records
       │  (pydantic)  │    │ rejected with  │
       └──────┬──────┘    │ reasons        │
              │           └────────────────┘
              ▼
       ┌──────────────┐   ┌──────────────┐   ┌────────────────┐
       │ Idempotent    │   │ SCD-2 dims   │   │ Event sourcing │
       │ upserts ON    │   │ (channels)   │   │ (item_events)  │
       │ natural keys  │   │              │   │                │
       └──────┬───────┘   └──────┬───────┘   └───────┬────────┘
              │                  │                    │
              └──────────┬───────┴────────────────────┘
                         ▼
                  ┌─────────────┐
                  │   DuckDB    │   gitignored, disposable
                  │ warehouse   │
                  └──────┬──────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   [sql/views.sql]  [aggregate.*]    [reports.*]
       │                 │                 │
       ▼                 ▼                 ▼
   Ad-hoc SQL       voice_profile     Markdown exports
   (`cdp query`)    (evidence for     (`cdp report`)
                    listing copy)
        │                 │                 │
        └─────────────────┴─────────────────┘
                          │
                          ▼
                 [optional] FastAPI layer
                (`cdp serve`, read-only)
```

## Schemas (classification)

| Schema | Purpose | Table examples |
|---|---|---|
| `core` | dimensions, ingest audit, reject quarantine | `channels`, `ingest_runs`, `rejected_records` |
| `catalog` | what we hold and its lifecycle | `items`, `item_events` |
| `supply` | inbound purchaseorders | `purchase_orders`, `po_line_items` |
| `sales` | listings, orders, engagement | `listings`, `orders`, `engagement_metric` |
| `insights` | content performance, behavioral aggregations | `content_pieces`, `voice_profile` |

## Why DuckDB

For this scale (tens of thousands of rows at this business's size read),
the right tool is the one that's already on the operators' laptops.
DuckDB's story here mirrors ClickHouse's at larger scale: same columnar
analytical model, same SQL surface. Moving to ClickHouse later means
copying the DDL, not re-architecting.

## Module layout

```
src/cdp_cli/
├── cli.py               # argparse-based CLI: init/build/ingest/validate/query/report/serve
├── db.py                # connection factory + schema init
├── validate.py          # pydantic models per source stream
├── ingest/
│   ├── base.py          # IngestJob: hash skip, audit row, quarantine, upsert contract
│   └── catalog.py       # SCD-2 channels, items, item_events
│   └── sales.py         # listings, engagement, orders
│   └── insights.py      # content_pieces, content_snapshot
├── analytics/
│   ├── aggregate.py     # insights.voice_profile derivation
│   └── reports.py       # markdown report renderers
└── api/
    └── main.py          # FastAPI read surface
```

## Testing strategy

- **Unit** (`test_validation.py` exercises pydantic rules: bad prices,
  missing sold fields, invalid enums)
- **Integration smoke** (`test_build_smoke.py` runs the full pipeline on
  the sample dataset and asserts every stream loads with zero rejects)
- **Idempotency** (`test_ingest_idempotency.py` runs ingest twice, expects
  zero new rows, zero new audit entries on the second run)
- **View sanity** (`test_views.py` spot-checks view outputs for
  self-consistency: totals across groups sum to source counts, sell-through
  groups stay within valid platforms)

## CI

GitHub Actions on push: install, run pytest on `sample_data/`, run a
fresh end-to-end `cdp build` as a smoke (fails the build if the warehouse
can't be built from scratch). No caching tricks — it's fast enough.

## Deployment

Containerized. `Dockerfile` runs the same `pip install -e .` as local.
`docker-compose.yml` maps `./sample_data` read-only so the container can
read canonical inputs but can't write data files (they belong on the
host or via mounted volume).
