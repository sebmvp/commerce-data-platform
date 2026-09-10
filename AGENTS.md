# Commerce Data Platform — engineering charter

This file is the durable project-scoped charter. Code wins when memory
disagrees. Update it when architecture or authority actually changes.

## Five invariants

1. **Real business truth is not synthetic data.** Private source records
   load into an isolated canonical database. Public JSONL is a separate
   demo/eval environment.
2. **The platform core is not the resale business.** Core provides
   reusable context infrastructure. Resale is the first vertical.
3. **PostgreSQL stores structured operational truth.** The Context Engine
   does not replace the database. The LLM does not replace the engine.
   Retrieval does not replace structured querying.
4. **Context is the product thesis.** For a question, assemble the
   objects, relationships, history, metrics, rules, evidence, and
   provenance required — and name missing required context.
5. **Public documentation explains software.** It speaks to operators and
   maintainers. It does not describe careers, interviews, or portfolios.

If future work contradicts these, document why the architecture changed.

## Thesis

A business is not a pile of documents.

Operational context is objects, relationships, history, metrics, rules,
provenance, and actions. For a question or decision, assemble only the
context required and explicitly identify what is missing.

## Platform core vs resale vertical

```
PLATFORM CORE                         RESALE VERTICAL (first, only production)
ContextBundle                         Items, listings, channels, orders
EntityRef / relationships / facts     Engagement, sourcing, resale intents
Events, evidence, provenance          Resale metrics and rules
Requirements + sufficiency            Source adapters (JSONL, item notes)
Generic assembly mechanics            Operator views (inventory, overview)
FastAPI / MCP / CLI adapters
Generic Context Inspector rendering
```

A new domain provides entities, relationships, intents/requirements,
resolvers, metrics, rules, evidence, and adapters. It does not rewrite
ContextBundle, generic sufficiency, or interface adapters.

Resale remains the only fully implemented vertical. Do not ship fake
second businesses as product features. A contract test may use an
in-test dummy domain to prove decoupling.

Core modules must not need to know what Grailed, watchers, or
acquisition_cost mean.

## Architectural principle

Structured operational truth uses structured retrieval.
Unstructured evidence uses search/retrieval.
Lexical retrieval / RAG is a context source, not the architecture.
The Context Engine decides what combination is required.

## Data environments

| Environment | Purpose | Database (typical) |
|-------------|---------|----------------------|
| Private / real | Canonical operational state of the real business | `cdp_private` |
| Public demo | Synthetic, scenario-rich, calibrated patterns | `cdp` |
| Held-out eval | Independent fictional world, different seed | `cdp_heldout` |
| Scale (optional) | Performance probing, not a production-scale claim | local only |

Canonical means a normalized operational representation with known
lineage, not “synthetic data we decided looks right.” The original raw
source remains evidence. Do not silently overwrite contradictory inputs.

Private raw input stays outside git (`/data/`, `.env`, `CDP_PRIVATE_SOURCE`).
`make ingest-private` loads it. `make clean` must not destroy it.

## Target flow

```
business sources
    → adapters
    → canonical operational model (PostgreSQL)
    → domain services
    → Context Engine
    → ContextBundle
    → FastAPI / MCP / CLI
    → React operator UI + grounded LLM
    → human-approved action
```

## Technology responsibility

Technologies must earn responsibilities. No collection-for-its-own-sake.

| Layer | Current responsibility | Not justified unless |
|-------|------------------------|----------------------|
| PostgreSQL | Canonical structured operational state | — |
| JSONL sample_data/ | Public synthetic seed / replay input | — |
| Context Engine | Assemble typed ContextBundle | — |
| FastAPI | Human/app HTTP adapter over shared services | — |
| MCP | Agent adapter over the same services | write/approve tools |
| React/TS | Operator UI + Context Inspector | full CRUD |
| Redis | none | async eval/model jobs, bundle cache, rate limits |
| DuckDB | removed from active architecture | large local Parquet / offline analytical bench |
| Graph DB / Kafka / Spark / Airflow / K8s / dbt / Polars | not adopted | a concrete capability they uniquely unlock |

## ContextBundle

`assemble_context(question, as_of?) → ContextBundle`

Must express: question, as_of, objects, relationships, facts, metrics,
history, applicable_rules, retrieved_evidence, provenance,
missing_context, sufficient.

`sufficient` is testable against known required concepts. Do not invent
confidence scores. When `sufficient` is false, qualify or abstain.

The engine is not arbitrary LLM-SQL and not `vector_search(question)`.

## Invariants (operational)

- Idempotent ingest (content-hash skip + natural-key upsert).
- Validation quarantine; rejects are never silent.
- One transaction per ingest run; mid-run exceptions roll back upserts
  and still write a durable `failed` audit row.
- Event-sourced items; listing_events for as-of reconstruction; SCD-2
  channels with half-open `[valid_from, valid_to)`.
- Full margin is not claimed.
- FACT / DERIVED / RECOMMENDATION / ACTION stay labeled.
- FastAPI and MCP share domain services / `assemble_context`; no
  duplicated domain logic.
- AI may propose; humans approve. No autonomous marketplace mutation.
- Public data is synthetic/sanitized. Private calibration stays local.

## Verification

Local tests passing is not remote CI passing.

After changing workflows, connection strings, or developer commands:
push, locate the GitHub Actions run for that HEAD, and require GREEN.
Do not report CI success from local execution alone.

GitHub Actions log redaction prints the disposable Postgres password
as `***`. Never copy that masked form into YAML, Makefile, VS Code,
compose files, or executable Python defaults. The local/CI password
is the literal `cdp`.

## Delegated authority

For this repository, Builder is authorized to change architecture,
schema, and structure; add migrations, Compose, CI, Makefile DX;
add React, FastAPI, MCP, bounded LLM, lexical baseline; expand
synthetic evaluation data; create multiple coherent commits and push
verified checkpoints.

Not authorized without a separate explicit instruction: spending money,
paid services, force-push / history rewrite, unrelated repositories,
secrets, or publishing private business records.

Continue through a milestone until its definition of done is met or a
genuine external blocker exists. Commits are recovery boundaries, not a
quota. Do not force-push.

## Developer surface

Makefile = developer lifecycle (`doctor`, `up`, `down`, `seed`,
`seed-heldout`, `ingest-private`, `test`, `eval`, `eval-heldout`,
`eval-compare`, `frontend`, `demo`, `demo-cli`, `clean`).

`cdp` = product behavior (`status`, `context`, `answer`, `eval`, `demo`,
`item`, `action`, `ingest-private`, `mcp`, …).

`make clean` must not destroy private/calibration data.

## Licensing

The public GitHub copy currently carries an MIT license (copyright 2026
Seb). Do not silently replace it with another OSI license or with invented
legal terms.
