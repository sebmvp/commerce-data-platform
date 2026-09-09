# Commerce Data Platform — engineering charter

This file is the durable project-scoped charter for Builder and any other
agent working in this repository. Code wins when memory disagrees. Update
this file when architecture or authority actually changes.

Private project memory lives in the existing Obsidian workspace:

```
~/Documents/Obsedian/Next Level/Commerce Data Platform/
```

Do not create another vault, scheduler, or competing project-state system.

## Project thesis

A business is not a pile of documents.

Operational context should be represented as objects, relationships,
history, metrics, rules, provenance, and actions.

For a question or decision, the system should assemble only the context
required to answer it and explicitly identify missing context.

## Architectural principle

Structured operational truth uses structured retrieval.
Unstructured evidence uses search/retrieval.
RAG is a context source, not the architecture.
The Context Engine decides what combination is required.

## Target flow

```
business sources
    → canonical operational model (PostgreSQL)
    → Context Engine
    → ContextBundle
    → FastAPI / MCP
    → LLM + React operator interface
    → grounded recommendation
    → human-approved action
```

## Quality principle

Technologies must earn responsibilities. No resume-keyword architecture.

| Layer | Current responsibility | Not justified unless |
|-------|------------------------|----------------------|
| PostgreSQL | Canonical structured operational state | — |
| JSONL sample_data/ | Public synthetic seed / replay input | — |
| Context Engine | Assemble typed ContextBundle | — |
| FastAPI | Human/app HTTP adapter over shared services | — |
| MCP | Agent adapter over the same services | write/approve tools |
| React/TS | Context Inspector + eval view | full CRUD |
| Redis | none | async eval/model jobs, bundle cache, rate limits |
| DuckDB | removed from active architecture | large local Parquet / offline analytical bench |
| Graph DB / Kafka / Spark / Airflow / K8s / dbt / Polars | not adopted | a concrete capability they uniquely unlock |

## Delegated authority

For this repository, Builder is authorized to:

- change architecture, schema, and repository structure
- migrate canonical state to PostgreSQL and delete obsolete store code
- add Alembic migrations, Docker Compose, GitHub Actions, Makefile DX
- add React + TypeScript, FastAPI, MCP, bounded LLM, honest RAG baseline
- add Redis only when a real runtime responsibility exists
- expand synthetic evaluation data (never commit private business data)
- create multiple coherent commits and push verified checkpoints

Not authorized without a separate explicit instruction: spending money,
paid services, force-push / history rewrite, unrelated repositories,
secrets, or publishing private business records.

Continue through a milestone until its definition of done is met or a
genuine external blocker exists. Commits are recovery boundaries, not a
quota. Do not force-push.

## ContextBundle

`assemble_context(question, as_of?) → ContextBundle`

The bundle must be able to express: question, as_of, objects, relationships,
facts, metrics, history, applicable_rules, retrieved_evidence, provenance,
missing_context, sufficient.

`sufficient` is testable against known required concepts. Do not invent
confidence scores. When `sufficient` is false, qualify or abstain.

The engine is not arbitrary LLM-SQL and not `vector_search(question)`.

## Invariants

- Idempotent ingest (content-hash skip + natural-key upsert).
- Validation quarantine; rejects are never silent.
- One transaction per ingest run; mid-run exceptions roll back upserts
  and still write a durable `failed` audit row.
- Event-sourced items; listing_events for as-of reconstruction; SCD-2 channels with half-open `[valid_from, valid_to)`.
- Full margin is not claimed.
- FACT / DERIVED / RECOMMENDATION / ACTION stay labeled.
- FastAPI and MCP share `business.py` / `assemble_context`; no duplicated
  domain logic.
- AI may propose; humans approve. No autonomous marketplace mutation.
- Public data is synthetic/sanitized. Private calibration stays local.

## Developer surface

Makefile = developer lifecycle (`doctor`, `up`, `down`, `seed`, `test`,
`eval`, `frontend`, `demo` visual inspector, `demo-cli`, `clean`).

`cdp` = product behavior (`status`, `context`, `eval`, `demo`, `item`, …).

`make clean` must not destroy private/calibration data.

## Licensing

The public GitHub copy currently carries an MIT license (copyright 2026
Seb). Do not silently replace it with another OSI license or with invented
legal terms. A move to all-rights-reserved / custom terms is a Sebastian
decision because the MIT grant is already published.

Preferred legal name if/when a copyright line is revised:
Sebastian Vaskes Pimentel. Public display name remains Seb.
