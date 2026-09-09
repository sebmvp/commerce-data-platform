# Developer notes

Design decisions worth knowing before extending this.

CLI surface: `init / build / ingest / validate / query / report / status / business / context / eval / demo / action / serve / mcp`.

Makefile is the developer lifecycle (`doctor`, `up`, `seed`, `test`, `eval`, `frontend`, `demo`).

## PostgreSQL is canonical

`CDP_DATABASE_URL` (default `postgresql://cdp:cdp@127.0.0.1:5432/cdp`) is
the operational store. JSONL under `sample_data/` is the public seed.
`make seed` / `cdp build --sample` rebuilds it. Do not hand-edit Postgres
in a way that cannot be reproduced from `schema/001_init.sql` + JSONL.

Alembic: `make migrate` / `alembic upgrade head`. Tests reset schemas
instead of running Alembic each time; the SQL files are the source.

## Ingest order matters

`cdp_cli.ingest.ALL_JOBS` runs in dependency order. See ARCHITECTURE.md.

## Idempotency has two levels

Content-hash skip per source file, plus `ON CONFLICT` upserts on natural keys.

## SCD-2 vs. ON CONFLICT

Channels use SCD-2. Ask `get_channel_as_of`. Listings/items/orders upsert.

## Adding a new source

1. Natural key + pydantic model in `validate.py`.
2. `IngestJob` subclass, registered in dependency order.
3. `CREATE TABLE` in `schema/001_init.sql` + Alembic revision.
4. Coverage in `tests/test_build_smoke.py`.
