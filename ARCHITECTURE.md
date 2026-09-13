# Architecture

How operational context is built and read. The README is the overview.

**CURRENT** is what the code does. **NEXT** is not in the repository.

The resale domain is the first implementation. Context contracts and
interface layers are kept separate from domain-specific resolvers,
metrics, and rules so additional operational domains can reuse the same
context machinery. The repository does not currently implement other
businesses.

## System

```mermaid
flowchart TD
  react[React] --> fastapi[FastAPI]
  fastapi --> librarian[Business Librarian]
  librarian --> tools[Domain read capabilities]
  tools --> engine[Context Engine]
  engine --> pg[(PostgreSQL)]
  engine --> bundle[ContextBundle + evidence]
  bundle --> gateway[ModelGateway]
  gateway --> fake[fake]
  gateway --> oai[openai_compatible]
  oai --> ollama[Ollama]
  oai --> vllm[vLLM]
  oai --> xai[xAI / compatible]
  gateway --> grounded[Validated grounded answer]
  grounded --> fastapi
  fastapi --> react
  react --> human[Human-approved sandbox action]
  human --> apply[Domain apply hook]
  apply --> pg
```

PostgreSQL owns structured operational truth. The engine assembles a
typed bundle for one question. Interfaces share that assembly; they do
not reimplement domain logic.

## Data boundaries

```mermaid
flowchart LR
  subgraph canonical [Private canonical]
    raw[Private raw sources] --> adapter[SourceAdapter]
    adapter --> batch[AdaptedBatch]
    batch --> runner[Ingest runner]
    runner --> private[(cdp_private Postgres)]
  end
  subgraph public [Public synthetic]
    calib[Private aggregate calibration knowledge] --> gen[Synthetic generator]
    gen --> demo[demo world]
    gen --> held[held-out world]
    demo --> publicdb[(public demo DB)]
    held --> helddb[(cdp_heldout)]
  end
```

Private rows never enter git. Public worlds copy lifecycle *patterns*,
not records.

## Core vs resale

```mermaid
flowchart TB
  subgraph core [Platform core]
    bundle[ContextBundle]
    suff[Sufficiency]
    prov[Provenance]
    assemble[Generic assembly]
    librarianCore[Generic Librarian loop]
    ground[Fail-closed grounding]
    actions[Action state machine]
    ifaces[FastAPI / MCP / CLI]
    inspector[Generic bundle renderer]
  end
  subgraph resale [Resale vertical]
    items[Items / listings / channels]
    intents[Resale intents]
    tools[Registered read tools]
    metrics[Resale metrics / rules]
    notesAdapter[Item-note adapters]
    views[Overview / inventory views]
    apply[Resale action apply]
  end
  resale --> core
```

## Resale object graph

```mermaid
graph LR
  Supplier --> Item
  Item --> Listing
  Listing --> Channel
  Listing --> Engagement
  Listing --> Order
  Item --> Note
  Item --> Recommendation
  Recommendation --> Action
```

## Question to context

```mermaid
sequenceDiagram
  participant Q as Question
  participant P as QuestionPlan
  participant D as Domain capabilities
  participant R as Resolvers
  participant E as Engine
  participant B as ContextBundle
  participant L as Grounded LLM
  Q->>P: deterministic parse or validated LLM plan
  P->>D: registered capability + subject
  D->>R: required concepts
  R->>E: objects, facts, history, evidence
  E->>B: sufficiency + provenance + evidence catalog
  alt insufficient
    B-->>Q: abstain, named gaps
  else sufficient
    B->>L: POST /answer over this exact bundle
    L-->>Q: answer + validated evidence refs
  end
```

Deterministic parsing remains CI, gold questions, and fallback. An optional
LLM planner may map natural phrasing onto registered capabilities. Neither
path may emit SQL. Invalid planner output falls back to the deterministic
parser — it is not guessed.

Grounding fails closed: malformed JSON, unknown citations, missing citations
on a non-abstaining answer, or an unregistered suggested action are not
trusted answers.

## Runtime interfaces

```mermaid
flowchart LR
  react[React] --> fastapi[FastAPI]
  agent[Agent] --> mcp[MCP]
  fastapi --> services[Shared services]
  mcp --> services
  cli[cdp CLI] --> services
  services --> engine[assemble_context]
  services --> pg[(PostgreSQL)]
```

## CURRENT vs NEXT

```
CURRENT
=======
private item-note adapter → isolated cdp_private
public JSONL worlds (demo / held-out) from synthetic/resale/
        → SourceAdapter → AdaptedBatch
        → ingest runner (hash skip, quarantine, one transaction, lineage)
        → PostgreSQL
        → domain services + context engine
        → CLI / FastAPI / MCP / React operator workspace
        → POST /answer (Librarian: registered tools + exact ContextBundle + grounding)
        → human-approved sandbox action → listing_events / item_events
        → recent_changes diffs live projection vs reconstructed prior snapshot
        → eval layers: assembly / planning / grounding / librarian (FakeProvider)
        → Data Steward profile/propose/review (PROPOSED contract only)

NEXT
====
marketplace listing/order/engagement adapters when those files exist
Redis only if evaluation/model runs become async jobs
operator-defined numeric pricing policy (not invented here)
```

## Technology decisions

| Tech | Decision | Responsibility |
|------|----------|----------------|
| PostgreSQL | **CURRENT** canonical store | Objects, history, ingest audit, sandbox actions, notes |
| JSONL sample_data/ | seed / replay input | Public synthetic worlds. Not a second truth. |
| DuckDB | **REMOVED** | No remaining distinct responsibility |
| SQLite actions | **REMOVED** | Actions live in `ops.actions` |
| Redis | **NOT YET** | No async job/cache/runtime need |
| dbt / Polars / Neo4j / Kafka / Spark / Airflow / K8s | **NOT ADOPTED** | No capability they uniquely unlock here |
| MCP | **CURRENT** | Typed tools over shared services |
| React/TS | **CURRENT** | Operator workspace (objects + Librarian) |
| LLM copilot | **CURRENT** | ModelGateway: fake default; openai_compatible for Ollama/vLLM/xAI; fail-closed grounding; Business Librarian; Data Steward proposals |
| Lexical retrieval baseline | **CURRENT (eval)** | TF-IDF vs gold ids. Not the architecture. Not RAG. |

## ContextBundle

`assemble_context(question, as_of?, domain?) → ContextBundle`

Fields: question, intent, as_of, objects, relationships, facts, metrics,
events, applicable_rules, applicable_policies, retrieved_evidence,
provenance, missing_context, sufficient, why, requirements,
evidence_units / evidence_catalog.

`sufficient` is true only when every required concept for the intent is
present. It is not a numeric confidence.

## Evaluation

`evals/context_questions.py` is GOLD / DEVELOPMENT (demo world).
`evals/heldout_questions.py` is HELD OUT (World B, different seed and SKUs).
Both score the engine, not an LLM.

`cdp eval --compare` / `GET /eval/compare` scores a lexical TF-IDF
baseline on the same ids. Call it lexical retrieval, not RAG.
`cdp eval --answers` / `GET /eval/answers` scores the grounded copilot
contract (FakeProvider) on those ids. `cdp eval --plan` and
`cdp eval --librarian` are separate layers. CI fails on engine FAIL or SKIP.
See docs/ai.md.
