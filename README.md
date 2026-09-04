# Commerce Data Platform

[![test](https://github.com/sebmvp/commerce-data-platform/actions/workflows/test.yml/badge.svg)](https://github.com/sebmvp/commerce-data-platform/actions/workflows/test.yml)

Turns messy resale operations data into a validated historical warehouse, then answers operational questions through typed tools with explicit metrics.

Fragmented sourcing, inventory, listing, order, engagement, and content files don't make a business state. This project builds one that can be rebuilt, inspected, and trusted when a source file is wrong.

## What it demonstrates

- Replay-safe ingest (content-hash skip + natural-key upserts)
- Pydantic validation with rejected-record quarantine, including malformed JSON
- Atomic run boundaries and orphan recovery
- SCD-2 channel history and event-sourced item state
- Ingest reconciliation (`read = loaded + rejected`) and a warehouse trust report
- Typed business tools: snapshot, attention queue, metric definitions — CLI and FastAPI

## Architecture

<img src="docs/architecture.svg" alt="Sources to ingest and validation, DuckDB warehouse, trust, metrics, business tools, future AI copilot" width="720"/>

```
sources → ingestion + validation → DuckDB warehouse
       → trust / reconciliation → metric definitions
       → business tools / API → (future) AI copilot
```

The copilot layer is not implemented. Tools already return provenance so one can be added later without stuffing warehouse rows into a prompt.

## Demo

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cdp demo
```

One command, about three minutes. It rebuilds the warehouse from bundled synthetic data, prints current business state and an attention queue, then ingests a **temp copy** of a source file with malformed JSON and a schema violation.

Valid rows stay in the catalog. Invalid rows land in quarantine. Trust stays readable. A replay does not duplicate items. Committed `sample_data/` is not modified.

Walkthrough: [docs/DEMO.md](docs/DEMO.md).

## Engineering decisions

1. **The warehouse is a cache.** Canonical JSONL keeps `raw_json` and origin file. Delete the DuckDB file and `cdp build` reconstructs it.
2. **A run is a transaction.** A mid-run exception rolls back partial upserts and still writes a durable `failed` audit row. Orphaned `running` rows are recovered on the next write.
3. **Metrics live in code.** `capital_tied_up_cny`, `stale_listing`, `watch_rate`, and the rest have definition, grain, null behavior, and limitations (`cdp business metric`).
4. **Recommendations are labeled.** Attention actions are heuristics on top of facts — not a score pretending to be a measurement.
5. **Fee-adjusted gross is not margin.** Acquisition cost is not subtracted; the output says so.

## Run locally

```bash
git clone https://github.com/sebmvp/commerce-data-platform
cd commerce-data-platform
docker compose up build
docker compose up api          # http://localhost:8000/docs
```

Without Docker:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,api]"
cdp build --sample
cdp status
cdp business snapshot
cdp business attention --limit 5
```

`--json` on business commands emits the structured payload (kind, data, provenance).

## Project boundaries

- Public data is synthetic / sanitized.
- This is not production infrastructure and not a scale claim.
- There is no live marketplace integration.
- An AI copilot is future work. The warehouse owns truth; tools expose it.

## Tests & CI

```bash
pytest -q
```

Covers validation, idempotency, atomicity, quarantine, reconciliation, business tools, adversarial fixtures, and the demo path. GitHub Actions runs the suite, a from-scratch `cdp build --sample`, and a Docker image smoke on every push to `main`.

## API

`cdp serve` — `/health`, `/inventory/*`, `/listings/performance`, `/insights/voice-profiles`, `/ingest/runs`, `/ingest/trust`, `/business/snapshot`, `/business/attention`, `/business/metrics`. Docs at `/docs`.

## Reference

| Layer | Path |
|-------|------|
| Schema | `schema/001_init.sql` |
| Views | `sql/views.sql` |
| Ingest | `src/cdp_cli/ingest/` |
| Metrics / tools | `src/cdp_cli/metrics.py`, `business.py` |
| Sample data | `sample_data/*.jsonl` |
| Detail | [ARCHITECTURE.md](ARCHITECTURE.md) · [docs/data-dictionary.md](docs/data-dictionary.md) · [docs/api.md](docs/api.md) |
