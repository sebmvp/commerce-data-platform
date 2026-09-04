# Demo

```bash
pip install -e ".[dev]"
cdp demo
```

Rebuilds `warehouse.duckdb` from `sample_data/`. About three minutes. Synthetic data only.

`cdp demo` does not edit committed source files. Bad input is staged in a temp copy.

## Story

1. **Build** — eight streams load; warehouse is a cache of JSONL.
2. **Business state** — owned / unlisted / listings / capital tied up (CNY) / realized revenue. Gross after fees is not margin.
3. **Attention** — deterministic queue. `LIST NEXT` on unlisted capital; `REVIEW PRICE OR CHANNEL` on stale listings. Numbers under each action are the facts.
4. **Failure** — malformed JSON + negative cost. Run stays successful; two rows quarantine; `catalog.items` still has 12.
5. **Trust** — `read = loaded + rejected`, no integrity alarms, same business counts.
6. **Replay** — canonical files unchanged → content-hash skip. No duplicate items. Quarantine remains.

Same commands by hand: `cdp build --sample`, `cdp business snapshot`, `cdp business attention --limit 5`, `cdp status`. `--json` if you want provenance payloads.

## After the demo

The warehouse on disk includes the quarantine rows from the dirty temp file. `rm warehouse.duckdb && cdp build --sample` returns to a clean build. `cdp demo` itself starts by removing the warehouse file.
