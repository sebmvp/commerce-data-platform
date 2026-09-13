# AI runtime

How models are called, what they may do, and where they stop.

This is operator/maintainer documentation. The default provider is fake.
A Grok/SuperGrok consumer subscription is not API access.

## Roles

LLMs may interpret, propose, summarize, reason, and explain.

They do not own canonical facts, temporal truth, validation,
reconciliation, numeric pricing, policy enforcement, permissions,
action state transitions, or external writes.

Generative output becomes operational only after deterministic
validation and, for actions, human approval.

Two bounded roles:

| Role | Input | Output | May write canonical state? |
|------|--------|--------|----------------------------|
| Analyst Agent | operator question | grounded answer + optional action proposal | no |
| Data Onboarding Agent | one explicit source file | `PROPOSED` source contract | no |

Deterministic ingest (`SourceAdapter` → validation → ingest runner →
PostgreSQL) remains the only production write path for source data.

## ModelGateway

```
CDP
  → ModelGateway
      → fake          (CI / default)
      → openai_compatible
            → Ollama        http://localhost:11434/v1
            → self-hosted vLLM   {host}/v1
            → xAI           https://api.x.ai/v1
            → other Chat Completions endpoints
```

There is one generic OpenAI-compatible transport. Vendor-specific
classes are not added unless a semantic difference requires them.

Configuration (aliases `CDP_LLM_*` still work):

```
CDP_MODEL_PROVIDER=fake | openai_compatible
CDP_MODEL_BASE_URL=http://localhost:11434/v1
CDP_MODEL_NAME=…
CDP_MODEL_API_KEY=          # optional for local endpoints
CDP_MODEL_TIMEOUT=30
CDP_MODEL_TEMPERATURE=0
CDP_MODEL_MAX_TOKENS=
CDP_MODEL_JSON_MODE=0     # opt-in; not assumed for local models
```

Local endpoints do not require a key. Keys are never logged.
`CDP_MODEL_PROVIDER=fake` stays fake even if a key is set.

xAI: set `CDP_MODEL_BASE_URL=https://api.x.ai/v1` and an **xAI API key**.
Do not scrape consumer Grok sessions.

Capabilities (JSON mode, structured output, tool calling, streaming)
are declared, not assumed. If a local model rejects `response_format`,
the client retries once without it. Parsing then uses JSON + schema
validation. Retries are bounded (2).

```bash
make ai-doctor   # provider, URL, model, reachability, Ollama tags — no secrets
make ai-smoke    # real/local provider only; never in CI; no business writes
```

`make ai-doctor` will not download a model. `make ai-smoke` refuses the
fake provider and refuses a remote endpoint with no key.

## Analyst Agent

Bounded loop (max 4 iterations) over **read tools registered by the
active domain**. The generic loop does not know resale vocabulary.

- business snapshot
- attention queue
- item state
- item history
- listing performance
- channel comparison
- recent changes
- data health
- note/policy evidence

No arbitrary SQL, Python, filesystem, or network.

A broad question such as “What should I focus on today?” uses snapshot
+ attention + data health. An item question loads that object subgraph.
“Knowing the whole business” means selective tool access, not dumping
the database into the prompt.

One `POST /answer`, `cdp answer`, or MCP `answer` returns:

- plan / tool trace (factual execution only)
- the exact ContextBundle used
- sufficiency
- grounded answer
- citations
- optional action proposal

The UI renders that payload. `GET /context` remains a separate
inspection path.

Modest follow-ups (“Why?”, “the second item”) re-resolve facts from
PostgreSQL. Conversation is not a source of truth.

## Grounding

The bundle publishes typed **evidence units** (object, fact, metric,
event, rule, note) with stable refs. Citations must exist in that
catalog for *that* bundle.

| Status | Meaning |
|--------|---------|
| ANSWERED / `grounded` | sufficient bundle, valid citations |
| ABSTAINED | insufficient context; model was not asked to invent |
| INVALID MODEL OUTPUT | malformed JSON, unknown refs, missing citations, bad action |

Malformed output is not trusted prose. Unknown refs fail closed (they
are not dropped while the rest survives). The model cannot override
`sufficient=false`. Suggested `propose_reprice` payloads may not include
a numeric price until an approved pricing policy exists.

## Onboarding Agent

CLI only:

```
cdp onboard profile <file>
cdp onboard propose <file>
cdp onboard review <proposal.json>
```

One explicitly selected file. No recursive scan. Deterministic profiling
runs first (columns, types, nulls, distinct counts, date-like fields,
candidate keys, samples). The model sees the profile, not every row.

Output status is always `PROPOSED`. Ambiguous fields become human
questions, not guessed mappings. Nothing is ingested until a human
approves a contract and a deterministic adapter uses it.

Do not send private sources to a remote model unless that provider and
source are explicitly authorized.

## Policy

Policy is operational control, not warehouse observation. Categories:

- **data contract** — what source data is valid
- **context** — evidence required to answer a capability
- **decision** — constraints on a recommendation
- **action** — what may be proposed/applied; human approval
- **security** — not implemented

Policies have stable ids/versions and appear on the ContextBundle.
PostgreSQL remains canonical business state. There is no policy database.

Pricing: AI may recommend `REVIEW PRICE`, `KEEP PRICE`, or
`INSUFFICIENT EVIDENCE`. There is no numeric markdown. The operator
enters a sandbox price. A later pricing model, if any, would be a
versioned policy; the LLM would explain it, not invent it at runtime.

## Evaluation layers (kept separate)

| Layer | Command |
|-------|---------|
| Context assembly | `cdp eval` |
| Question/tool planning | `cdp eval --plan` |
| Grounding validity | `cdp eval --answers` |
| Agent task success | `cdp eval --analyst` |

These are not combined into one accuracy number. Real-model evaluation
is optional (`make ai-smoke`) and is not CI.
