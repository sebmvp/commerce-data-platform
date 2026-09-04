# Commerce Data Platform

[![test](https://github.com/sebmvp/commerce-data-platform/actions/workflows/test.yml/badge.svg)](https://github.com/sebmvp/commerce-data-platform/actions/workflows/test.yml)

An operational data and intelligence system for a small multi-channel
**resale commerce** workflow — not just an ETL demo.

It turns messy sourcing / inventory / listing / sales / engagement JSONL into a
validated DuckDB warehouse, then answers operational questions through typed
tools with explicit metric definitions and provenance. The long-term direction
is a grounded AI business copilot that retrieves current truth via those tools
— never by stuffing warehouse rows into a prompt.

**Python · DuckDB · FastAPI · Docker · pytest · GitHub Actions**

- 8 ingestion streams
- idempotent ingestion (re-running a build on unchanged sources loads no new rows)
- content-hash change detection
- validation + rejected-record quarantine (including malformed JSON)
- **atomic run boundaries** (mid-run failure rolls back partial loads)
- historical / SCD-2 modeling
- ingest auditing + **read=loaded+rejected reconciliation**
- business snapshot + inventory attention queue (FACT / DERIVED / RECOMMENDATION)
- analytics + API layer

## Architecture

<img src="docs/architecture.svg" alt="Pipeline architecture: sources → ingestion → validation/quarantine → audit → DuckDB warehouse → history, analytics, event state → CLI/FastAPI" width="720"/>

```
messy sources → trustworthy ingest → warehouse → semantic metrics
    → typed business tools → (future) AI copilot → evaluated recommendations
```

## Quick start

```bash
git clone https://github.com/sebmvp/commerce-data-platform
cd commerce-data-platform
docker compose up build        # builds the warehouse from the bundled synthetic data
docker compose up api          # FastAPI read layer at http://localhost:8000/docs
```

Or without Docker:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,api]"
cdp build --sample
cdp status
cdp business snapshot
cdp business attention --limit 5
cdp report funnel
```

Interviewer-facing walkthrough: **[docs/DEMO.md](docs/DEMO.md)** (≈3–5 minutes).

Actual output:

```
$ cdp build --sample
Schema initialized: warehouse.duckdb
  [ok ] core.channels                read=  3 loaded=  3 rejected=  0
  [ok ] catalog.items                read= 12 loaded= 12 rejected=  0
  [ok ] catalog.item_events          read= 39 loaded= 39 rejected=  0
  [ok ] sales.listings               read=  9 loaded=  9 rejected=  0
  [ok ] sales.engagement_metric      read= 71 loaded= 71 rejected=  0
  [ok ] sales.orders                 read=  6 loaded=  6 rejected=  0
  [ok ] insights.content_pieces      read=  9 loaded=  9 rejected=  0
  [ok ] insights.content_snapshot    read=  9 loaded=  9 rejected=  0
Refreshed 1 voice profile version(s)
Build complete.

$ cdp status
db: warehouse.duckdb (...)
  items              12
  ...
trust: OK
  - no integrity alarms
reconciliation (recent runs):
  source                       status    read  load   rej balanced
  catalog.items                success     12    12     0 yes
  ...

$ cdp business attention --limit 3
kind: recommendation
RECOMMENDATIONS (heuristic):
  [list_next] stone-cargo-l: ... capital is idle.
  ...
```

Before processing a source file, the loader computes a content hash and checks the most recent successful ingest. Files whose contents have not changed are skipped, which keeps repeated builds from inserting duplicate records:

```
$ cdp build --sample
  core.channels                    unchanged (skipped)
  catalog.items                    unchanged (skipped)
  ...                              unchanged (skipped)
  rejected_records   0      ingest_runs  still 8 (skip runs are not counted)
```

The bundled dataset is intentionally small — it is a **deterministic demo fixture** (generator committed, safe to share), not a scale claim. See [docs/assumptions.md](docs/assumptions.md) for the distribution reasoning.

## Engineering decisions

1. **Canonical inputs preserved.** Every row keeps its raw source payload (`raw_json`) and origin file. The DuckDB file is a cache — delete it and `cdp build` rebuilds losslessly.
2. **Idempotent ingest.** Natural-key upserts plus content-hash skip detection: unchanged sources are not re-processed, re-runs never duplicate rows.
3. **Validation before insert.** Pydantic models per stream; failing rows are quarantined to `core.rejected_records` with reasons — never silently dropped.
4. **Atomic runs.** Each source ingest is one transaction; a mid-run exception rolls back partial upserts and still records a durable `failed` audit row. Orphaned `running` rows are recovered on the next write path.
5. **Event-sourced supply chain.** `catalog.item_events` is append-only truth; `catalog.items` is the latest projection.
6. **SCD-2 dimensions.** Fee/standing history is versioned so point-in-time queries return the state as of any date.
7. **Explicit metrics.** Operational numbers (`capital_tied_up_cny`, `inventory_age_days`, `stale_listing`, …) have definitions, grain, null behavior, and limitations in code (`cdp business metric`).
8. **Typed business tools over arbitrary SQL.** `cdp business snapshot|attention|health` return structured payloads with provenance — the substrate for a future copilot. No LLM in-tree yet; that is intentional until the foundation is trustworthy.
9. **Honest economics.** Fee-adjusted gross is labeled as such. Full margin is not claimed while acquisition-cost allocation and fee modeling are incomplete.

## Data quality

Every run writes an `core.ingest_runs` audit record (source, read/loaded/rejected counts, duration, content hash). Rejected rows are stored with the validation error and raw payload, so bad data is inspectable rather than invisible. `cdp status` reconciles `read = loaded + rejected` and surfaces trust alarms (orphaned runs, unbalanced successes).

## Tests & CI

```bash
pytest -q          # unit + integration: atomicity, quarantine, reconciliation, business tools, adversarial fixtures
```

GitHub Actions runs the suite, a from-scratch `cdp build --sample` smoke build, and a Docker image smoke build on every push to `main`.

## API

`cdp serve` starts a FastAPI read layer over the warehouse: `/health`, `/inventory/summary`, `/inventory/unlisted`, `/listings/performance`, `/insights/voice-profiles`, `/ingest/runs`, `/ingest/trust`, `/business/snapshot`, `/business/attention`, `/business/metrics` (interactive docs at `/docs`).

## Things testing caught

- Ingest re-runs duplicating rows before content-hash skip detection was added — now covered by an idempotency test that builds twice and asserts stable counts.
- A CI Docker smoke step where `build` and `status` ran in separate `--rm` containers, so the warehouse vanished between steps — the workflow now shares a volume, and the failure mode is documented in the commit history.
- Malformed JSON aborting an entire batch — quarantine now continues past corrupt lines (`tests/test_ingest_malformed.py`).
- Mid-run exceptions leaving partial loads — runs are transactional (`tests/test_ingest_atomicity.py`).

## Reference

| Layer | Path | Role |
|-------|------|------|
| Schema | `schema/001_init.sql` | DDL — source of truth |
| Views | `sql/views.sql` | Analytics surface (`v_*`) |
| CLI | `src/cdp_cli/cli.py` | `init / build / ingest / validate / query / report / serve` |
| Ingest | `src/cdp_cli/ingest/` | Per-source loaders, pydantic validation, run audit |
| Sample data | `sample_data/*.jsonl` | Synthetic — safe to commit |
| Docs | [ARCHITECTURE.md](ARCHITECTURE.md) · [docs/data-dictionary.md](docs/data-dictionary.md) · [docs/api.md](docs/api.md) | Detail |

`cdp report <inventory|pricing|funnel>` exports markdown analytics to `reports/`.
