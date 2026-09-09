# Demo

```bash
pip install -e ".[dev,api]"
make up
make seed
cdp demo
```

Builds an **isolated Postgres database** from `sample_data/`. About three minutes. Synthetic data only.

`cdp demo` does not edit committed source files and does not touch the caller's `CDP_DATABASE_URL`. Bad input is staged in a temp copy.

## Story

1. **Build** — JSONL streams load into PostgreSQL.
2. **Business state** — owned / unlisted / listings / capital tied up (CNY) / realized revenue. Gross after fees is not margin.
3. **Attention** — deterministic queue. `LIST NEXT` on unlisted capital; `REVIEW PRICE OR CHANNEL` on stale listings. Numbers under each action are the facts.
4. **Item** — `stone-cargo-l` retrieved as an object: identity, acquisition, age, empty listings/orders, event timeline. Facts, not a recommendation.
5. **Sandbox action** — the top recommendation is proposed, then human-approved into `ops.actions`. Catalog tables do not change.
6. **Failure** — malformed JSON + negative cost. Run stays successful; two rows quarantine; `catalog.items` still has 12.
7. **Trust** — `read = loaded + rejected`, no integrity alarms, same business counts.
8. **Replay** — canonical files unchanged → content-hash skip. No duplicate items. Quarantine remains.

Same commands by hand: `cdp build --sample`, `cdp business snapshot`, `cdp business attention --limit 5`, `cdp business item stone-cargo-l`, `cdp business history stone-cargo-l`, `cdp context "Should I reprice stone-cargo-l?"`, `cdp eval`, `cdp status`. `--json` if you want provenance payloads.

Then `cdp serve` + `make frontend` for the Context Inspector.

## After the demo

The isolated database is dropped when the command exits. `cdp build --sample` seeds the configured `CDP_DATABASE_URL` for later `cdp business` / `cdp status` use.
