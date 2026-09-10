# Architecture

How operational context is built and read. The README is the overview.

**CURRENT** is what the code does. **NEXT** is not in the repository.

```
CURRENT
=======
canonical JSONL seed (sample_data/)
        │
        ▼
IngestJob per source
  hash skip → validate → quarantine / upsert
  one transaction per run
        │
        ▼
PostgreSQL (canonical operational store)
  core · catalog · supply · sales · insights · ops
        │
        ├─ observability.trust_report
        ├─ metrics.METRICS
        └─ business tools
                │
                ▼
        context engine
          intents → objects / links / events / metrics / rules
          selective unstructured notes (ops.notes)
          missing_context + sufficient (rule-based)
                │
                ├─ CLI   cdp status | context | eval | demo | action | mcp
                ├─ FastAPI  /context  /eval  /business/*  /ingest/trust
                ├─ MCP stdio  assemble_context + read tools (no approve/execute)
                └─ React Context Inspector  (web/)

NEXT (partial)
==============
grounded copilot: FakeProvider default; env provider when CDP_LLM_API_KEY is set
lexical RAG baseline vs Context Engine on the same gold ids (`cdp eval --compare`)
full-context dump comparison and LLM-judged answers — not started
Redis only if evaluation/model runs become async jobs
```

## Technology decisions

| Tech | Decision | Responsibility |
|------|----------|----------------|
| PostgreSQL | **CURRENT** canonical store | Objects, history, ingest audit, sandbox actions, notes |
| JSONL sample_data/ | seed / replay input | Public synthetic world. Not a second truth. |
| DuckDB | **REMOVED** | No remaining distinct responsibility |
| SQLite actions | **REMOVED** | Actions live in `ops.actions` |
| Redis | **NOT YET** | No async job/cache/runtime need |
| dbt / Polars / Neo4j / Kafka / Spark / Airflow / K8s | **NOT ADOPTED** | No capability they uniquely unlock here |
| MCP | **CURRENT** | Typed read tools over shared services |
| React/TS | **CURRENT** | Context Inspector + evaluation view |
| LLM copilot | **CURRENT (thin)** | FakeProvider default; env provider when keyed |
| RAG baseline | **CURRENT (eval)** | Lexical TF-IDF vs gold ids. Not the architecture |

## ContextBundle

`assemble_context(question, as_of?) → ContextBundle`

Fields: question, intent, as_of, objects, relationships, facts, metrics,
events, applicable_rules, retrieved_evidence, provenance, missing_context,
sufficient.

`sufficient` is true only when every required concept for the intent is
present. It is not a numeric confidence.

## Invariants

See [AGENTS.md](AGENTS.md). Idempotent ingest, quarantine, atomic runs,
event-sourced items, SCD-2 channels, no invented margin, human-gated
sandbox actions.

## Gold evaluation

`evals/context_questions.py` scores the engine, not an LLM.
`cdp eval` / `GET /eval` run the catalog against the seeded world.
`cdp eval --compare` / `GET /eval/compare` scores a lexical TF-IDF
baseline on the same ids. CI fails on engine FAIL or SKIP. Listing as-of,
channel comparison, and listing-performance are implemented intents.
