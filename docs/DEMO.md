# Demo runbook (3–5 minutes)

Reproducible interviewer demo. Every command is real and tested.
Synthetic data only — never private business information.

## Story (one breath)

A resale operation produces fragmented data across sourcing, inventory,
listings, sales, and engagement. This platform turns those sources into a
validated historical business model. Because ingestion is replay-safe,
observable, and auditable, operational questions (and eventually an AI
copilot) can reason over business state without stale spreadsheets.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,api]"
```

## Act 1 — Build (~45s)

```bash
cdp build --sample
cdp status
```

Show: eight streams loaded, `trust: OK`, reconciliation `read = load + rej`.

## Act 2 — Business state (~45s)

```bash
cdp business snapshot
```

Show: owned/unlisted, active + stale listings, capital tied up (CNY),
realized revenue. Note the labels: FACT vs DERIVED, and that
`realized_gross_after_fees_usd` is **not** full margin.

## Act 3 — Malformed input + quarantine (~60s)

```bash
# append one corrupt line (restore afterward)
printf '{this is not json}\n' >> sample_data/catalog_items.jsonl
cdp ingest catalog.items --force
cdp business health
cdp query "SELECT error_code, detail FROM core.rejected_records ORDER BY created_at DESC LIMIT 5"
git checkout -- sample_data/catalog_items.jsonl
```

Show: run still processes; corrupt line quarantined; trust stays readable.

## Act 4 — Idempotent replay (~20s)

```bash
cdp build --sample
# unchanged sources → skipped; counts stable
cdp status
```

## Act 5 — Operational question (~60s)

```bash
cdp business attention --limit 5
cdp business metric capital_tied_up_cny
```

Show: attention queue with explicit reasons (`unlisted_owned`, `stale_listing`),
heuristic RECOMMENDATIONS labeled separately from FACT rows, and a metric
definition with grain/null/limitations.

## Act 6 — AI copilot (not built yet)

Same question through a typed tool-using agent. The tool contracts already
exist (`get_business_snapshot`, `get_inventory_attention_queue`,
`get_ingest_health`, `explain_metric`) with provenance payloads (`--json`).

```bash
cdp business attention --json | head
```

## Mapping

| Moment | Engineering property | Business meaning |
|--------|----------------------|------------------|
| Act 1  | rebuildable cache    | reproducible state |
| Act 3  | quarantine + atomic runs | one bad export never blocks ops |
| Act 4  | content-hash idempotency | safe to re-run |
| Act 5  | explicit metrics + tools | defensible answers |
| Act 6  | typed tools + provenance | copilot substrate |

## Checklist

- [ ] `pytest -q` green
- [ ] restore `sample_data` after Act 3
- [ ] keep total time ≤ 5 minutes
