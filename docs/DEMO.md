# Demo

The public demo is the operator workspace: Overview → object → Context → sandbox action.

```bash
pip install -e ".[dev,api]"
make doctor
make up
make seed
make demo
```

Open **http://127.0.0.1:5173**. About a minute after seed. Synthetic data only. The
environment badge should read **DEMO · SYNTHETIC**.

`make demo` starts FastAPI and the workspace. Ctrl-C stops them.
`cdp demo` is a different command: the isolated CLI reliability story.

## Product story (visual)

1. **Overview** — owned / listed / sold, capital, and the attention queue. Names first, SKUs second.
2. **Attention item** — click a row. The why line is the reason it is on the queue.
3. **Object view** — identity, listings, engagement, orders, timeline, sandbox action.
4. **Ask** — “Should I reprice this?” from the object, or type it on Context.
5. **Interpreted plan** — registered capability + subject. Not SQL.
6. **Sufficiency** — SUFFICIENT or INSUFFICIENT, with required evidence named.
7. **Grounded answer** — FakeProvider by default; a real model only if `CDP_LLM_API_KEY` is set. Citations must exist in the same ContextBundle.
8. **Action** — price review is not a numeric markdown. Enter a sandbox price, propose, human-approve. Internal `listing_events` change. No marketplace write.
9. **Ask again** — Context reflects the new asking price / history.
10. **Reset** — `make reset-demo` rebuilds the demo world.

Insufficient path: `Should I reprice stone-cargo-l?` Missing listing and engagement. The grounded path abstains.

Temporal path: `What was the active listing state for j4-military-s two weeks ago?` Uses the world clock, not today's date.

Evaluation: TOTAL / PASS / FAIL / SKIP on the gold catalog, Context Engine vs lexical retrieval, and the FakeProvider grounded-answer contract on the same ids.

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
5. **Sandbox action** — propose then human-approve into `ops.actions`. Approval can apply an internal reprice/history change. It does not write a marketplace.
6. **Failure** — malformed JSON + negative cost. Quarantine is visible.
7. **Trust / replay** — content-hash skip, no duplicate items.

Same commands by hand: `cdp build --sample`, `cdp business snapshot`,
`cdp business attention --limit 5`, `cdp business item stone-cargo-l`,
`cdp context "Should I reprice stone-cargo-l?"`, `cdp answer "Should I reprice stone-cargo-l?"`,
`cdp eval`, `cdp status`.

## After the visual demo

`make demo` leaves the seeded `cdp` database in place for later `cdp context`
/ `cdp eval` use. `cdp demo` drops its isolated database on exit.
