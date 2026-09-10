# Developer notes

Design decisions worth knowing before extending this.

Makefile is the developer lifecycle. `cdp` is product behavior.

## Commands

### Makefile

| Command | What it does |
|---------|----------------|
| `make doctor` | REQUIRED vs OPTIONAL checks (Python, package, Node, Postgres, seed, optional Docker/LLM) |
| `make up` | Start Postgres (compose if Docker works, else whatever is on :5432) |
| `make down` | Stop compose services |
| `make seed` | Rebuild the demo world into `CDP_DATABASE_URL` |
| `make reset-demo` | Alias of `make seed`; clears sandbox actions |
| `make seed-heldout` | Rebuild World B into `cdp_heldout` |
| `make ingest-private` | Load `CDP_PRIVATE_SOURCE` into isolated `cdp_private` |
| `make test` | pytest |
| `make eval` | Gold Context Engine evaluation (strict) |
| `make eval-heldout` | Held-out scenario validation |
| `make eval-compare` | Engine vs lexical retrieval baseline |
| `make demo` | Operator workspace (API + Vite). Prints `http://127.0.0.1:5173` |
| `make demo-cli` | Isolated CLI reliability story |
| `make test-e2e` | Playwright |
| `make migrate` | Alembic upgrade head |
| `make clean` | Safe caches only — never private/calibration data |

### cdp

| Command | What it does |
|---------|----------------|
| `cdp ingest-private` | Private item notes → `cdp_private` (set `CDP_PRIVATE_SOURCE`) |
| `cdp status` | Health snapshot + ingest reconciliation |
| `cdp context "…"` | Assemble a ContextBundle (`--intent`, `--sku`, `--as-of`, `--json`) |
| `cdp answer "…"` | Grounded answer over that bundle (abstains if insufficient) |
| `cdp eval` | GOLD / DEVELOPMENT catalog |
| `cdp eval --heldout` | HELD OUT catalog (needs the held-out world) |
| `cdp eval --compare` | Engine vs lexical retrieval baseline |
| `cdp business snapshot \| attention \| health \| item \| history \| channel` | Typed business tools |
| `cdp demo` | Isolated warehouse → decision → quarantine story |
| `cdp mcp` | MCP stdio server (read tools only) |
| `cdp action propose \| list \| get \| approve \| reject` | Sandbox actions; no marketplace mutation |
| `cdp serve` | FastAPI (`/context`, `/answer`, `/eval`, `/eval/compare`, `/business/*`) |
| `cdp build --sample` | Schema + ingest from `CDP_DATA` |
| `cdp init / ingest / validate / query / report / tables` | Warehouse operations |

VS Code tasks wrap the Makefile (Doctor, Start system, Run tests, Run eval,
Run held-out eval, Run demo). FastAPI debug launch is in `.vscode/launch.json`.

## PostgreSQL is canonical

`CDP_DATABASE_URL` (default `postgresql://cdp:cdp@127.0.0.1:5432/cdp`) is
the operational store. JSONL under `sample_data/` is the public demo seed;
`sample_data_heldout/` is World B. `make seed` / `cdp build --sample` rebuilds
the connected database. Do not hand-edit Postgres in a way that cannot be
reproduced from `schema/001_init.sql` + JSONL.

Alembic: `make migrate` / `alembic upgrade head`. Tests reset schemas
instead of running Alembic each time; the SQL files are the source.

World clock: `sample_data/world.json` (`as_of`) freezes listing ages and
relative phrases. `CDP_AS_OF=now` uses the wall clock.

A missing `CDP_LLM_API_KEY` does not block deterministic evaluation.

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
