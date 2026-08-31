# Developer notes

Design decisions worth knowing before extending this.

## The warehouse file is a cache

`warehouse.duckdb` is gitignored and rebuildable. Never hand-edit it in
a way that can't be reproduced from `schema/001_init.sql` +
`sample_data/*.jsonl`. If a migration is needed, bump the schema file,
delete the .duckdb, and re-run `cdp build`.

## Ingest order matters

`cdp_cli.ingest.ALL_JOBS` runs in dependency order:
1. dimensions (`core.channels`) before facts that reference them
2. `catalog.items` before `catalog.item_events` / `sales.listings`
3. `catalog.item_events` and `sales.*` before `insights.*` aggregations

`ingest/base.py` enforces this at load time by checking that referenced
rows exist (`event references unknown item sku`).

## Idempotency has two levels

- **Row level**: every file is hashed (SHA-256). If today's file
  content-hash matches the last successful ingest run for that source,
  the whole file is skipped (see `IngestJob._already_succeeded`).
- **Batch level**: every row upserts on a natural key
  (`ON CONFLICT ... DO UPDATE`), so re-running on an unchanged file is
  also a no-op even without the hash skip.

## Validation is pre-insert, not post-hoc

Pydantic models (one per stream) define the shape. Every row failing
goes to `core.rejected_records` with the pydantic error serialized —
visible in `cdp query "SELECT * FROM core.rejected_records"` or
`cdp validate`.

## SCD-2 vs. ON CONFLICT

Channels use SCD-2 (`valid_from` / `valid_to`) because fees and standing
actually change over time and point-in-time queries matter. Items,
listings, orders use `ON CONFLICT DO UPDATE` — a listing's *price* can
change, but we don't need the history of that change in the warehouse
(it lives in the source platforms' "listing updated at" APIs if we ever
need it).

## Adding a new source

1. Pick a natural key.
2. Add a pydantic model in `src/cdp_cli/validate.py` with constraints.
3. Add a `IngestJob` subclass in the right aggregation module.
4. Register it in `src/cdp_cli/ingest/__init__.py` **in dependency
   order**.
5. Add a `CREATE TABLE` in `schema/001_init.sql` with matching columns
   + upsert key. Add end-to-end coverage in `tests/test_build_smoke.py`.

## The voice profile is evidence, not vibes

`insights.voice_profile` is aggregated *from* what actually converted.
When writing new listing copy, read the current profile:
`SELECT summary_md FROM insights.voice_profile WHERE is_current`.
Don't trust it as instruction — trust the underlying numbers
(`avg_watchers`, `avg_conversion`) as evidence.
