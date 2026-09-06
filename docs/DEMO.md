# Demo

```bash
pip install -e ".[dev]"
cdp demo
```

Builds an **isolated temp warehouse** from `sample_data/`. About three minutes. Synthetic data only.

`cdp demo` does not edit committed source files and does not touch `warehouse.duckdb` or `CDP_DB`. Bad input is staged in a temp copy.

## Story

1. **Build** — eight streams load; warehouse is a cache of JSONL.
2. **Business state** — owned / unlisted / listings / capital tied up (CNY) / realized revenue. Gross after fees is not margin.
3. **Attention** — deterministic queue. `LIST NEXT` on unlisted capital; `REVIEW PRICE OR CHANNEL` on stale listings. Numbers under each action are the facts.
4. **Item** — `stone-cargo-l` retrieved as an object: identity, acquisition, age, empty listings/orders, event timeline. Facts, not a recommendation.
5. **Failure** — malformed JSON + negative cost. Run stays successful; two rows quarantine; `catalog.items` still has 12.
6. **Trust** — `read = loaded + rejected`, no integrity alarms, same business counts.
7. **Replay** — canonical files unchanged → content-hash skip. No duplicate items. Quarantine remains.

Same commands by hand: `cdp build --sample`, `cdp business snapshot`, `cdp business attention --limit 5`, `cdp business item stone-cargo-l`, `cdp business history stone-cargo-l`, `cdp status`. `--json` if you want provenance payloads.

## After the demo

The isolated warehouse is deleted when the command exits. Nothing is left on disk. `cdp build --sample` is the command that writes `warehouse.duckdb` for later `cdp business` / `cdp status` use.
