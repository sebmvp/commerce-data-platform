# Commerce Data Platform

[![test](https://github.com/sebmvp/commerce-data-platform/actions/workflows/test.yml/badge.svg)](https://github.com/sebmvp/commerce-data-platform/actions/workflows/test.yml)

Operational business questions depend on objects, relationships, history, metrics, and rules. Treating that world as documents to embed is convenient and often wrong.

This project builds a **business context engine** for a small multi-channel resale operation: represent the operational world directly, then assemble only the context a decision needs — including an explicit statement when required context is missing.

## What exists now

```
sources → ingest + validation → DuckDB warehouse (rebuildable cache)
       → metric definitions + typed business tools
       → context engine (objects, links, events, rules, missing_context)
       → CLI / FastAPI / MCP (read tools)
       → sandbox actions (propose → human approve/reject)
```

- Replay-safe ingest (content-hash skip + natural-key upserts)
- Pydantic validation with rejected-record quarantine, including malformed JSON
- Atomic run boundaries and orphan recovery
- SCD-2 channel history (as-of lookup) and event-sourced item state
- Ingest reconciliation (`read = loaded + rejected`) and a warehouse trust report
- Typed business tools: snapshot, attention queue, item + history, channel as-of, metric definitions
- Context engine: bounded intents → structured `ContextBundle` with provenance and missing-context disclosure
- Context-assembly eval catalog (`evals/context_questions.py`)
- Sandbox action log: propose → human approve/reject (does not mutate the warehouse)
- MCP stdio server: the same read tools as FastAPI; no approve/execute

## What is next (not implemented)

Grounded LLM copilot, RAG baseline comparison, React operator UI, PostgreSQL operational store. See [ARCHITECTURE.md](ARCHITECTURE.md).

## Architecture

<img src="docs/architecture.svg" alt="Sources to ingest and validation, warehouse, trust, metrics, business tools, context engine" width="720"/>

The warehouse is not the product. It is how operational facts become queryable. The context engine is the layer a later copilot will call.

## Demo

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cdp demo
```

One command, about three minutes. Isolated temp warehouse from bundled synthetic data (your `warehouse.duckdb` / `CDP_DB` is not deleted). Then:

```bash
cdp build --sample
cdp context "Should I reprice j4-military-s?"
cdp context "Should I reprice stone-cargo-l?"
cdp context "What should I focus on today?"
```

The listed item returns objects, links, metrics, and rules. The unlisted item returns `sufficient: false` and `missing_context: listing, engagement` instead of inventing a market.

Walkthrough: [docs/DEMO.md](docs/DEMO.md).

## Engineering decisions

1. **Structured context is retrieved, not embedded.** Exact object lookup, relationships, metrics, and rules — not vector search over serialized tables.
2. **The warehouse is a cache.** Canonical JSONL keeps `raw_json` and origin file. Delete the DuckDB file and `cdp build` reconstructs it.
3. **A run is a transaction.** A mid-run exception rolls back partial upserts and still writes a durable `failed` audit row.
4. **Metrics live in code.** `capital_tied_up_cny`, `stale_listing`, `watch_rate`, and the rest have definition, grain, null behavior, and limitations (`cdp business metric`).
5. **Missing context is a first-class output.** Sufficiency is rule-based. There is no invented confidence score.
6. **Fee-adjusted gross is not margin.** Acquisition cost is not subtracted; the output says so.

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
pip install -e ".[dev,api,mcp]"
cdp build --sample
cdp status
cdp business snapshot
cdp context "What should I focus on today?"
cdp business attention --limit 5
cdp business channel grailed --as-of 2025-06-01
```

`--json` emits the structured payload.

## Project boundaries

- Public data is synthetic / sanitized.
- This is not production infrastructure and not a scale claim.
- There is no live marketplace integration.
- There is no LLM in this repository yet. MCP exposes the context engine; a copilot is still later.

## Tests & CI

```bash
pytest -q
```

Covers validation, idempotency, atomicity, quarantine, reconciliation, business tools, attention-queue eval, context assembly, MCP adapter, adversarial fixtures, and the demo path. GitHub Actions runs the suite, a from-scratch `cdp build --sample`, and a Docker image smoke on every push to `main`.

## API

`cdp serve` — `/health`, `/inventory/*`, `/listings/performance`, `/insights/voice-profiles`, `/ingest/runs`, `/ingest/trust`, `/context`, `/business/snapshot`, `/business/attention`, `/business/metrics`, `/business/items/{sku}`, `/business/items/{sku}/history`, `/business/actions`. Docs at `/docs`.

`cdp mcp` — stdio MCP server over the same read tools. See [docs/mcp.md](docs/mcp.md).

## Reference

| Layer | Path |
|-------|------|
| Schema | `schema/001_init.sql` |
| Views | `sql/views.sql` |
| Ingest | `src/cdp_cli/ingest/` |
| Metrics / tools | `src/cdp_cli/metrics.py`, `business.py` |
| Context engine | `src/cdp_cli/context/` |
| MCP adapter | `src/cdp_cli/mcp/` |
| Eval catalog | `evals/context_questions.py` |
| Sample data | `sample_data/*.jsonl` |
| Detail | [ARCHITECTURE.md](ARCHITECTURE.md) · [docs/data-dictionary.md](docs/data-dictionary.md) · [docs/api.md](docs/api.md) · [docs/mcp.md](docs/mcp.md) |
