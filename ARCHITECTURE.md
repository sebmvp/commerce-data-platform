# Architecture

How operational context is built and read. The README is the overview.

**CURRENT** is what the code does. **NEXT** is not in the repository.

```
CURRENT
=======
canonical JSONL seed (sample_data/ demo world; sample_data_heldout/ World B)
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
          world clock for ages and "two weeks ago"
                │
                ├─ CLI   cdp status | context | answer | eval | demo | action | mcp
                ├─ FastAPI  /context  /answer  /eval  /eval/compare  /business/*
                ├─ MCP stdio  assemble_context + read tools (no approve/execute)
                └─ React Context Inspector  (web/)
                     sufficiency, why, objects, history, provenance,
                     grounded answer, gold eval, lexical comparison

NEXT
====
LLM-judged answers on the same ids
full-context dump comparison
persisted previous snapshot (Q08 / H08 still abstain)
sandbox propose/approve in the Inspector
Redis only if evaluation/model runs become async jobs
```

## Technology decisions

| Tech | Decision | Responsibility |
|------|----------|----------------|
| PostgreSQL | **CURRENT** canonical store | Objects, history, ingest audit, sandbox actions, notes |
| JSONL sample_data/ | seed / replay input | Public synthetic worlds. Not a second truth. |
| DuckDB | **REMOVED** | No remaining distinct responsibility |
| SQLite actions | **REMOVED** | Actions live in `ops.actions` |
| Redis | **NOT YET** | No async job/cache/runtime need |
| dbt / Polars / Neo4j / Kafka / Spark / Airflow / K8s | **NOT ADOPTED** | No capability they uniquely unlock here |
| MCP | **CURRENT** | Typed read tools over shared services |
| React/TS | **CURRENT** | Context Inspector + evaluation view |
| LLM copilot | **CURRENT (thin)** | FakeProvider default; env provider when keyed; abstains if insufficient |
| Lexical retrieval baseline | **CURRENT (eval)** | TF-IDF vs gold ids. Not the architecture. Not RAG. |

## ContextBundle

`assemble_context(question, as_of?) → ContextBundle`

Fields: question, intent, as_of, objects, relationships, facts, metrics,
events, applicable_rules, retrieved_evidence, provenance, missing_context,
sufficient, why.

`sufficient` is true only when every required concept for the intent is
present. It is not a numeric confidence.

## Invariants

See [AGENTS.md](AGENTS.md). Idempotent ingest, quarantine, atomic runs,
event-sourced items, SCD-2 channels, no invented margin, human-gated
sandbox actions.

## Evaluation

`evals/context_questions.py` is GOLD / DEVELOPMENT (demo world).
`evals/heldout_questions.py` is HELD OUT (World B, different seed and SKUs).
Both score the engine, not an LLM. Reports always use total / pass / fail / skip
against the catalog denominator.

`cdp eval --compare` / `GET /eval/compare` scores a lexical TF-IDF
baseline on the same ids. CI fails on engine FAIL or SKIP.
