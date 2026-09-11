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
  sources[Business sources] --> adapters[Source adapters]
  synth[Public synthetic worlds] --> adapters
  adapters --> pg[(PostgreSQL canonical store)]
  pg --> services[Domain services]
  services --> structured[Structured context]
  services --> search[Unstructured evidence]
  structured --> engine[Context Engine]
  search --> engine
  engine --> bundle[ContextBundle]
  bundle --> api[FastAPI]
  bundle --> mcp[MCP]
  bundle --> cli[CLI]
  api --> ui[React operator UI]
  api --> llm[Grounded LLM]
  llm --> api
  api --> ui
  ui --> human[Human-approved actions]
```

PostgreSQL owns structured operational truth. The engine assembles a
typed bundle for one question. Interfaces share that assembly; they do
not reimplement domain logic.

## Data boundaries

```mermaid
flowchart LR
  raw[Private raw sources] --> private[(cdp_private)]
  raw --> calib[Private calibration patterns]
  calib --> gen[Synthetic generator]
  gen --> demo[demo world]
  gen --> held[held-out world]
  gen --> scale[optional scale profile]
  demo --> public[(public demo DB)]
  held --> helddb[(cdp_heldout)]
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
    ifaces[FastAPI / MCP / CLI]
    inspector[Generic bundle renderer]
  end
  subgraph resale [Resale vertical]
    items[Items / listings / channels]
    intents[Resale intents]
    metrics[Resale metrics / rules]
    notesAdapter[Item-note adapters]
    views[Overview / inventory views]
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
        → POST /answer (plan + exact ContextBundle + grounding)
        → human-approved sandbox action → listing_events / item_events
        → recent_changes diffs live projection vs reconstructed prior snapshot

NEXT
====
LLM-judged answers on the same ids
marketplace listing/order/engagement adapters when those files exist
Redis only if evaluation/model runs become async jobs
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
| React/TS | **CURRENT** | Operator UI + Context Inspector |
| LLM copilot | **CURRENT** | FakeProvider default; env provider when keyed; fail-closed grounding; POST /answer |
| Lexical retrieval baseline | **CURRENT (eval)** | TF-IDF vs gold ids. Not the architecture. Not RAG. |

## ContextBundle

`assemble_context(question, as_of?, domain?) → ContextBundle`

Fields: question, intent, as_of, objects, relationships, facts, metrics,
events, applicable_rules, retrieved_evidence, provenance, missing_context,
sufficient, why, requirements.

`sufficient` is true only when every required concept for the intent is
present. It is not a numeric confidence.

## Evaluation

`evals/context_questions.py` is GOLD / DEVELOPMENT (demo world).
`evals/heldout_questions.py` is HELD OUT (World B, different seed and SKUs).
Both score the engine, not an LLM.

`cdp eval --compare` / `GET /eval/compare` scores a lexical TF-IDF
baseline on the same ids. Call it lexical retrieval, not RAG.
CI fails on engine FAIL or SKIP.
