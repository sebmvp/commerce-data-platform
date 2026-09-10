# Demo

Primary demo is the visual Context Inspector.

```bash
pip install -e ".[dev,api]"
make doctor
make up
make seed
make demo
```

Open **http://127.0.0.1:5173**. About a minute after seed. Synthetic data only.

`make demo` starts FastAPI and the inspector. Ctrl-C stops them.
`cdp demo` is a different command: the isolated CLI reliability story.

## Product story (visual)

1. **Question** — default is `Should I reprice j4-military-s?`
2. **Sufficiency** — SUFFICIENT. The why line names the evidence required.
3. **Grounded answer** — FakeProvider by default; a real model only if
   `CDP_LLM_API_KEY` is set. Still bound to the ContextBundle.
4. **Objects / relationships** — business names first (item → listing → channel).
   Raw ids are behind a toggle.
5. **Insufficient** — ask `Should I reprice stone-cargo-l?` Missing listing
   and engagement. The grounded path abstains.
6. **Object** — open `j4-military-s` for current state, listings, timeline.
7. **Temporal** — `What was the active listing state for j4-military-s two weeks ago?`
   Uses the world clock, not today's date.
8. **Evaluation** — TOTAL / PASS / FAIL / SKIP on the gold catalog, plus
   Context Engine vs lexical retrieval on the same ids.

## Engineering reliability deep dive (CLI)

Not the headline. Useful when someone asks how ingest fails.

```bash
make demo-cli
# or: cdp demo
```

Builds an **isolated Postgres database** from `sample_data/`. Does not
edit committed files and does not touch the caller's `CDP_DATABASE_URL`.

1. **Build** — JSONL streams load into PostgreSQL.
2. **Business state** — owned / unlisted / listings / capital tied up (CNY) / realized revenue. Gross after fees is not margin.
3. **Attention** — deterministic queue.
4. **Item** — `stone-cargo-l` as an object: identity, acquisition, empty listings.
5. **Sandbox action** — propose then human-approve into `ops.actions`. Catalog tables do not change.
6. **Failure** — malformed JSON + negative cost. Quarantine is visible.
7. **Trust / replay** — content-hash skip, no duplicate items.

Same commands by hand: `cdp build --sample`, `cdp business snapshot`,
`cdp business attention --limit 5`, `cdp business item stone-cargo-l`,
`cdp context "Should I reprice stone-cargo-l?"`, `cdp answer "Should I reprice stone-cargo-l?"`,
`cdp eval`, `cdp status`.

## After the visual demo

`make demo` leaves the seeded `cdp` database in place for later `cdp context`
/ `cdp eval` use. `cdp demo` drops its isolated database on exit.
