# Architecture

How operational context is built and read. The README is the overview.

**CURRENT** is what the code does. **NEXT** is not in the repository.

```
CURRENT
=======
canonical JSONL (sample_data/)
        │
        ▼
IngestJob per source
  hash skip → validate → quarantine / upsert
  one transaction per run
        │
        ▼
DuckDB (gitignored cache)
  core · catalog · supply · sales · insights
        │
        ├─ observability.trust_report
        ├─ metrics.METRICS
        └─ business tools (snapshot, attention, item, history, channel as-of, health)
                │
                ▼
        context engine
          intents → objects / links / events / metrics / rules
          missing_context + sufficient (rule-based)
                │
                ├─ CLI  cdp status | business | context | demo | action | mcp
                ├─ FastAPI  /ingest/trust  /business/*  /context  /business/actions
                └─ MCP stdio  assemble_context + read tools (no approve/execute)

NEXT (not implemented)
======================
grounded copilot (provider-abstracted LLM)
RAG baseline over serialized business text (comparison, not replacement)
React operator UI
PostgreSQL operational store (actions + mutable objects)
```

## Technology decisions (2026-09-08)

Re-evaluated against the original thesis: a business is not a pile of documents, and the warehouse is not the product.

| Tech | Decision | Responsibility |
|------|----------|----------------|
| DuckDB | **DEMOTE** as architectural center; **KEEP** as current analytical/fact cache | Rebuildable laptop warehouse from JSONL. Distinct from an application database. Remove later if ingest writes canonical objects elsewhere and this role disappears. |
| PostgreSQL | **ADOPT later**, not this slice | Concurrent operational objects, actions, approvals, agent-run records. Introducing an empty Postgres now would be two databases for show. SQLite already holds sandbox actions. |
| SQLite actions | **EVOLVE** | Correct propose/approve model. Migrate into Postgres when that store exists. |
| dbt | **DO NOT ADOPT** | Not enough reusable SQL transform/metric complexity to justify a second modeling layer. `metrics.py` + tools remain the source of truth. |
| Polars | **DO NOT ADOPT** | Ingest is still row-at-a-time pydantic, not a dataframe path. |
| Graph DB | **DO NOT ADOPT** | Object + link semantics are modeled in the context engine. Scale does not justify Neo4j. |
| MCP | **current** | Typed tools over the context engine, sharing services with FastAPI. Not a second domain layer. |
| React/TS | **REQUIRED later** | Operator visibility into the same objects/links the engine assembles. |
| LLM copilot | **REQUIRED later** | After context bundles + missing-context behavior are stable. Fake provider for tests. |
| RAG baseline | **REQUIRED later** | Honest comparison: serialize business state to chunks vs context engine, same questions, same model. Do not sabotage the baseline. |
| Kafka/Spark/Airflow/K8s/Redis | **REJECT** | No capability they uniquely unlock at this scale. |

DuckDB stays because a reviewer can rebuild it with zero services, and the context engine currently reads it. That is a real responsibility, not nostalgia. It is no longer the story.

## Source domains

Eight JSONL streams, dependency-ordered in `ALL_JOBS`:

| Source | File | Destination |
|---|---|---|
| channels | `channels.jsonl` | `core.channels` (SCD-2) |
| items | `catalog_items.jsonl` | `catalog.items` |
| item events | `item_events.jsonl` | `catalog.item_events` (append-only) |
| listings | `listings.jsonl` | `sales.listings` |
| engagement | `engagement_metrics.jsonl` | `sales.engagement_metric` |
| orders | `orders.jsonl` | `sales.orders` |
| content | `content_pieces.jsonl` | `insights.content_pieces` |
| content snapshots | `content_snapshots.jsonl` | `insights.content_snapshot` |

`supply.*` tables exist in DDL for purchase orders; they are not loaded from the public sample set.

## Ingest lifecycle

`IngestJob.run` (`src/cdp_cli/ingest/base.py`):

1. SHA-256 the file. `run_idempotency_key = sha256(source + file_hash)`. If a successful run already exists for that key, skip.
2. Open a transaction. Insert `core.ingest_runs` with `status='running'`.
3. For each line: parse JSON (malformed → quarantine `malformed_json`); pydantic-validate (fail → `schema_violation`); `upsert` on the natural key. Loader-level referential misses become `load_error`.
4. Commit. Mark the run `success` with read/loaded/rejected counts.
5. On unexpected exception: rollback upserts from that attempt, then write a durable `failed` audit row in a new transaction.

`recover_orphaned_runs` turns leftover `running` rows into `failed` before the next write session (`init_schema` and ingest start).

`--force` bypasses the hash skip.

## Context model

The engine speaks a small domain language, not table names:

| Kind | Examples |
|------|----------|
| OBJECT | Item, Listing, Channel, Order, EngagementObservation, IngestRun, Recommendation, Action |
| LINK | HAS_LISTING, ON_CHANNEL, HAS_ENGAGEMENT, RESULTED_IN, TARGETS, DERIVED_FROM |
| EVENT | ordered, received, listed, sold, listing_opened |
| ACTION | propose_list, propose_reprice, propose_channel_change, mark_reviewed (sandbox) |

A `ContextBundle` contains: question, intent, as_of, objects, relationships, facts, metrics, events, applicable_rules, retrieved_evidence, provenance, missing_context, sufficient.

`sufficient` is true only when every required concept for the intent is present. It is not a numeric confidence.

Bounded intents in v1: `reprice_item`, `focus_today`, `explain_attention`, `item_state`, `item_history`, `data_health`, `recent_changes`. Free-form NL planning is not claimed.

Unstructured retrieval (`retrieved_evidence`) is empty until there is genuinely unstructured evidence to fetch. Structured facts are not vectorized.

## Context-assembly eval

`evals/context_questions.py` is the start of the comparison suite. Implemented rows assert that the engine retrieved required objects or disclosed missing context. Unimplemented rows (temporal listing as-of, multi-hop channel history) stay in the catalog so the gap is visible.

A later RAG baseline will answer the same ids. If retrieval wins some categories, that result will be reported.

## Validation and quarantine

Pydantic models live in `validate.py`. Rejects go to `core.rejected_records` with `error_code`, `detail`, `raw_json`, and `run_id`. A run can be `success` with `rows_rejected > 0` — processed, not necessarily clean. All-reject success is a trust *warning*, not a hard fail.

## Idempotency

- **Batch:** content-hash skip, above.
- **Row:** `ON CONFLICT` upserts on natural keys. Replaying an unchanged file is a no-op even without the skip.

## History

- **SCD-2** on `core.channels`: fee/standing changes close the open row at the *successor's* `valid_from` (not ingest wall-clock). Intervals are half-open `[valid_from, valid_to)` with `valid_to` null meaning current. `get_channel_as_of` is the point-in-time API. Listing/order rows stamp the version that was current at ingest; that key is not automatically as-of `listed_at`/`order_at`.
- **Event sourcing** on `catalog.item_events`: append-only truth. `catalog.items` is the latest projection.

## Warehouse trust

`observability.trust_report` is the definition of healthy used by `cdp status`, `/ingest/trust`, and `get_ingest_health`.

Hard fail: orphaned `running` rows, or a `success` run that breaks `read = loaded + rejected`.

Warnings (do not flip `ok`): historical `failed` runs that rolled back, all-reject successes.

## Metrics and business tools

`metrics.py` is the registry. Tools in `business.py` must implement those definitions. The context engine calls those tools; it does not duplicate their SQL.

| Tool | Kind | Question |
|---|---|---|
| `get_business_snapshot` | derived | What is the operation holding right now? |
| `get_inventory_attention_queue` | recommendation | What deserves a look, and why? |
| `get_ingest_health` | fact | Can I trust this warehouse? |
| `explain_metric` | fact | What does this number mean? |
| `get_item` | fact | What is this item right now? |
| `get_item_history` | fact | What happened to this item over time? |
| `get_channel_as_of` | fact | What channel version (fee/standing) covered this instant? |
| `assemble_context` | context | What operational context does this question require, and is it present? |

Attention ranking is deterministic: unlisted owned (by capital, then age) → stale listings → high watch_rate with zero offers. Actions (`LIST NEXT`, `REVIEW PRICE OR CHANNEL`, `CONSIDER REPRICE`) are heuristics labeled separately from the metric columns.

`realized_gross_after_fees_usd` is not full margin.

Sandbox actions (`cdp action`, `/business/actions`) are a separate SQLite log. They record propose → human approve/reject. They do not mutate DuckDB or any marketplace.

## Surfaces

- CLI: `init / build / ingest / validate / query / report / status / business / context / action / demo / serve / mcp`
- API: view-backed inventory/listing/insight routes, plus `/ingest/trust`, `/context`, and `/business/*`
- MCP: `cdp mcp` stdio server, same read tools, no approve/execute
- Demo: `cdp demo` builds an isolated temp warehouse from `sample_data/` (never unlinks the configured DB)

## Tests

Covers validation, smoke build, idempotency, malformed JSON, atomicity, views, observability, business tools, labeled attention-queue eval, context assembly, context eval catalog, MCP adapter, adversarial fixtures, demo path. CI: pytest, `cdp build --sample`, Docker image smoke.
