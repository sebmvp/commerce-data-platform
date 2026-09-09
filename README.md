# Commerce Data Platform

[![test](https://github.com/sebmvp/commerce-data-platform/actions/workflows/test.yml/badge.svg)](https://github.com/sebmvp/commerce-data-platform/actions/workflows/test.yml)

A business is not a pile of documents. Operational questions depend on
objects, relationships, history, metrics, rules, and an explicit statement
when required context is missing.

This repo is a **business context engine** for a small multi-channel resale
operation. Structured facts are retrieved as structured facts. Unstructured
notes are searched. RAG is not the architecture.

## What exists

```
synthetic JSONL seed
        → validated ingest (quarantine, idempotent, one transaction per run)
        → PostgreSQL canonical operational store
        → typed business tools + Context Engine
        → ContextBundle (objects, links, history, rules, missing_context)
        → CLI / FastAPI / MCP
        → React Context Inspector + gold evaluation
        → sandbox actions (propose → human approve/reject)
```

DuckDB is no longer in the active architecture. Redis is not used: nothing
here is an async job queue yet.

## Developer loop

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,api,mcp]"
make doctor
make up          # docker compose postgres, or a local Postgres on :5432
make seed
make test
make eval
make demo
```

Then, in another terminal:

```bash
cdp serve        # http://127.0.0.1:8000/docs
make frontend    # http://127.0.0.1:5173  Context Inspector
```

`Makefile` is the developer lifecycle. `cdp` is product behavior
(`status`, `context`, `eval`, `demo`, `business item <sku>`).

## Demo

```bash
cdp demo
cdp context "Should I reprice j4-military-s?"
cdp context "Should I reprice stone-cargo-l?"
cdp context "What do seller notes say about stone-cargo-l?"
```

The listed item returns objects, links, metrics, rules, and seller notes.
The unlisted item returns `sufficient: false` and `missing_context` instead
of inventing a market.

## Boundaries

- Public data is synthetic / sanitized.
- This is not a scale claim and not live marketplace integration.
- There is no LLM in this repository. MCP exposes the context engine;
  a grounded copilot is next.
- The published LICENSE is MIT (already on GitHub). That is not an
  invitation to treat private business data as public.

## Reference

| Layer | Path |
|-------|------|
| Charter | [AGENTS.md](AGENTS.md) |
| Schema | `schema/001_init.sql` + Alembic |
| Context engine | `src/cdp_cli/context/` |
| Eval catalog | `evals/context_questions.py` |
| Inspector | `web/` |
| Detail | [ARCHITECTURE.md](ARCHITECTURE.md) · [docs/DEMO.md](docs/DEMO.md) |
