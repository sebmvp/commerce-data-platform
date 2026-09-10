# Commerce Data Platform

[![test](https://github.com/sebmvp/commerce-data-platform/actions/workflows/test.yml/badge.svg)](https://github.com/sebmvp/commerce-data-platform/actions/workflows/test.yml)

Business questions depend on exact operational state and relationships,
not merely semantically similar documents.

This project models that business context explicitly — items, listings,
channels, events, metrics, rules, notes — and assembles only the evidence
required for a question. When required context is missing, it says so.

![Context Inspector](docs/screenshots/context-inspector.png)

## How it works

```
synthetic JSONL seed
        → validated ingest (quarantine, idempotent, one transaction per run)
        → PostgreSQL canonical operational store
        → Context Engine → ContextBundle
        → CLI / FastAPI / MCP / React Context Inspector
```

RAG is a possible context *source*, not the architecture. Redis is not used:
nothing here is an async job queue yet.

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,api,mcp]"
make doctor
make up          # docker compose postgres, or a local Postgres on :5432
make seed
make test
make eval        # TOTAL 20 / PASS 20 / FAIL 0 / SKIP 0
make demo        # http://127.0.0.1:5173  visual Context Inspector
```

`make demo` starts the API and inspector. `cdp demo` is the CLI/system
behavior story (isolated database). `Makefile` is the developer lifecycle;
`cdp` is product behavior (`status`, `context`, `eval`, `demo`,
`business item <sku>`).

## Evaluation

Gold questions score `assemble_context`, not an LLM. Cases include
current facts, as-of listing state, channel comparison, listing
performance, missing context, and a hybrid structured + note question.

`cdp eval --compare` (or `GET /eval/compare`) runs the same ids against
a lexical TF-IDF baseline over serialized warehouse rows. That baseline
is an honest comparison, not the architecture: it has no vector database
and does not see attention-queue recommendations. Hybrid note questions
are expected to tie; multi-hop and missing-context disclosure are not.

`cdp answer` runs a thin grounded path over that bundle. The default
provider is fake. A real model is used only when `CDP_LLM_API_KEY` is
set. Insufficient bundles abstain.

## Boundaries

- Public data is synthetic / sanitized. Private resale records stay local.
- This is not a scale claim and not live marketplace integration.
- Grounded answers use the ContextBundle. Default provider is fake; no keys in the repo.
- The published LICENSE is MIT (already on GitHub). That is not an
  invitation to treat private business data as public.

## Reference

| Layer | Path |
|-------|------|
| Charter | [AGENTS.md](AGENTS.md) |
| Schema | `schema/001_init.sql` + Alembic |
| Public world | `scripts/generate_public_world.py` |
| Context engine | `src/cdp_cli/context/` |
| Eval catalog | `evals/context_questions.py` |
| RAG baseline | `evals/rag_baseline.py` |
| Inspector | `web/` |
| Detail | [ARCHITECTURE.md](ARCHITECTURE.md) · [docs/DEMO.md](docs/DEMO.md) |
