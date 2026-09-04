# Architecture

How the warehouse is built and read. The README is the overview.

```
canonical JSONL (sample_data/)
        │
        ▼
IngestJob per source
  hash skip → validate → quarantine / upsert
  one transaction per run
        │
        ▼
DuckDB (gitignored cache)
  core · catalog · supply · sales · insights
        │
        ├─ observability.trust_report
        ├─ metrics.METRICS
        └─ business tools (snapshot, attention, health, explain_metric)
                │
                ├─ CLI  cdp status | business | demo
                └─ FastAPI  /ingest/trust  /business/*
                        │
                        └─ (future) AI copilot — not in this repo
```

## Source domains

Eight JSONL streams, dependency-ordered in `ALL_JOBS`:

| Source | File | Destination |
|---|---|---|
| channels | `channels.jsonl` | `core.channels` (SCD-2) |
| items | `catalog_items.jsonl` | `catalog.items` |
| item events | `item_events.jsonl` | `catalog.item_events` (append-only) |
| listings | `listings.jsonl` | `sales.listings` |
| engagement | `engagement_metrics.jsonl` | `sales.engagement_metric` |
| orders | `orders.jsonl` | `sales.orders` |
| content | `content_pieces.jsonl` | `insights.content_pieces` |
| content snapshots | `content_snapshots.jsonl` | `insights.content_snapshot` |

`supply.*` tables exist in DDL for purchase orders; they are not loaded from the public sample set.

## Ingest lifecycle

`IngestJob.run` (`src/cdp_cli/ingest/base.py`):

1. SHA-256 the file. `run_idempotency_key = sha256(source + file_hash)`. If a successful run already exists for that key, skip.
2. Open a transaction. Insert `core.ingest_runs` with `status='running'`.
3. For each line: parse JSON (malformed → quarantine `malformed_json`); pydantic-validate (fail → `schema_violation`); `upsert` on the natural key. Loader-level referential misses become `load_error`.
4. Commit. Mark the run `success` with read/loaded/rejected counts.
5. On unexpected exception: rollback upserts from that attempt, then write a durable `failed` audit row in a new transaction.

`recover_orphaned_runs` turns leftover `running` rows into `failed` before the next write session (`init_schema` and ingest start).

`--force` bypasses the hash skip.

## Validation and quarantine

Pydantic models live in `validate.py`. Rejects go to `core.rejected_records` with `error_code`, `detail`, `raw_json`, and `run_id`. A run can be `success` with `rows_rejected > 0` — processed, not necessarily clean. All-reject success is a trust *warning*, not a hard fail.

## Idempotency

- **Batch:** content-hash skip, above.
- **Row:** `ON CONFLICT` upserts on natural keys. Replaying an unchanged file is a no-op even without the skip.

## History

- **SCD-2** on `core.channels`: fee/standing changes close `valid_to` and open a new version. Point-in-time queries should filter `valid_from/valid_to`; as-of helpers are not a separate API yet.
- **Event sourcing** on `catalog.item_events`: append-only truth. `catalog.items` is the latest projection.

## Warehouse trust

`observability.trust_report` is the definition of healthy used by `cdp status`, `/ingest/trust`, and `get_ingest_health`.

Hard fail: orphaned `running` rows, or a `success` run that breaks `read = loaded + rejected`.

Warnings (do not flip `ok`): historical `failed` runs that rolled back, all-reject successes.

## Metrics and business tools

`metrics.py` is the registry. Tools in `business.py` must implement those definitions.

| Tool | Kind | Question |
|---|---|---|
| `get_business_snapshot` | derived | What is the operation holding right now? |
| `get_inventory_attention_queue` | recommendation | What deserves a look, and why? |
| `get_ingest_health` | fact | Can I trust this warehouse? |
| `explain_metric` | fact | What does this number mean? |

Attention ranking is deterministic: unlisted owned (by capital, then age) → stale listings → high watch_rate with zero offers. Actions (`LIST NEXT`, `REVIEW PRICE OR CHANNEL`, `CONSIDER REPRICE`) are heuristics labeled separately from the metric columns.

`realized_gross_after_fees_usd` is not full margin.

## Surfaces

- CLI: `init / build / ingest / validate / query / report / status / business / demo / serve`
- API: view-backed inventory/listing/insight routes, plus `/ingest/trust` and `/business/*` which call the same Python tools
- Demo: `cdp demo` rebuilds from `sample_data/`, prints state, stages dirty input in a temp copy, shows quarantine, replays

## Future AI boundary

A copilot would call the tools above at question time and cite provenance. It would not embed warehouse rows, generate arbitrary SQL, or write back. Nothing in that layer exists in this repository.

## Why DuckDB

The public fixture is small by design. A file the reviewer can rebuild on a laptop beats a service they cannot. The SQL surface is ordinary enough to move later if the data ever required it. That is not a scale claim.

## Tests

Validation, smoke build, idempotency, malformed JSON, atomicity, views, observability, business tools, adversarial fixtures, demo path. CI: pytest, `cdp build --sample`, Docker image smoke.
