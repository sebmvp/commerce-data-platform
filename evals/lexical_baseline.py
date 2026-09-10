"""Lexical retrieval baseline over serialized operational rows.

This is an evaluation experiment, not the context architecture. The corpus
is a text dump of warehouse tables (items, listings, events, notes,
channels, ingest). It does not include attention-queue recommendations or
precomputed answers. Retrieval is TF-IDF cosine in the standard library —
no vector database, no API embeddings, and no LLM generation — so the
comparison is deterministic.

Call it a lexical retrieval baseline, not RAG, unless retrieve → prompt →
generate is actually implemented.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from cdp_cli.clock import reference_now

_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
DEFAULT_K = 8


def _rows(con, sql: str, params: list | None = None) -> list[dict[str, Any]]:
    rel = con.execute(sql, params or [])
    cols = [c[0] for c in rel.description]
    return [dict(zip(cols, row)) for row in rel.fetchall()]


def _fmt(kind: str, **fields: Any) -> dict[str, Any]:
    parts = [f"kind={kind}"]
    sku = fields.get("sku") or fields.get("object_id")
    for key, value in fields.items():
        if value is None or value == "":
            continue
        parts.append(f"{key}={value}")
    ident = (
        fields.get("note_id")
        or fields.get("listing_id")
        or fields.get("event_id")
        or fields.get("order_id")
        or fields.get("run_id")
        or fields.get("channel_key")
        or fields.get("sku")
        or kind
    )
    return {
        "id": f"{kind}:{ident}",
        "kind": kind,
        "sku": None if sku is None else str(sku),
        "text": " ".join(parts),
    }


def build_corpus(con) -> list[dict[str, Any]]:
    """Serialize current operational rows. Derived queues stay out."""
    now = reference_now()
    chunks: list[dict[str, Any]] = []
    for row in _rows(
        con,
        """
        SELECT sku, product, status, condition, acquisition_cost_cny,
               target_price_usd, size, variant
        FROM catalog.items
        """,
    ):
        chunks.append(_fmt("item", **row))
    for row in _rows(
        con,
        """
        SELECT
          i.sku, l.listing_id, l.status, l.price_usd, l.listed_at, l.sold_at,
          ch.platform,
          CASE WHEN l.listed_at IS NULL THEN NULL
               ELSE date_diff('day', l.listed_at, CAST(? AS timestamp))
          END AS listing_age_days,
          coalesce(sum(em.views), 0) AS views,
          coalesce(sum(em.watchers), 0) AS watchers,
          coalesce(sum(em.offers), 0) AS offers,
          CASE WHEN coalesce(sum(em.views), 0) = 0 THEN NULL
               ELSE round((sum(em.watchers)::numeric / sum(em.views)), 4)
          END AS watch_rate
        FROM sales.listings l
        JOIN catalog.items i ON i.item_id = l.item_id
        LEFT JOIN core.channels ch ON ch.channel_key = l.channel_key
        LEFT JOIN sales.engagement_metric em ON em.listing_id = l.listing_id
        GROUP BY i.sku, l.listing_id, l.status, l.price_usd, l.listed_at,
                 l.sold_at, ch.platform
        """,
        [now],
    ):
        chunks.append(_fmt("listing", **row))
    for row in _rows(
        con,
        """
        SELECT i.sku, e.event_id, e.event_type, e.event_at
        FROM catalog.item_events e
        JOIN catalog.items i ON i.item_id = e.item_id
        """,
    ):
        chunks.append(_fmt("item_event", **row))
    for row in _rows(
        con,
        """
        SELECT i.sku, le.event_id, le.listing_id, le.event_type, le.event_at,
               le.price_usd, le.status
        FROM sales.listing_events le
        JOIN sales.listings l ON l.listing_id = le.listing_id
        JOIN catalog.items i ON i.item_id = l.item_id
        """,
    ):
        chunks.append(_fmt("listing_event", **row))
    for row in _rows(
        con,
        """
        SELECT i.sku, o.order_id, o.price_usd, o.status, o.order_at, ch.platform
        FROM sales.orders o
        LEFT JOIN catalog.items i ON i.item_id = o.item_id
        LEFT JOIN core.channels ch ON ch.channel_key = o.channel_key
        """,
    ):
        chunks.append(_fmt("order", **row))
    for row in _rows(
        con,
        """
        SELECT note_id, kind AS note_kind, object_type, object_id, title, body
        FROM ops.notes
        """,
    ):
        chunks.append(_fmt("note", **row))
    for row in _rows(
        con,
        """
        SELECT channel_key, platform, handle, standing, fee_pct,
               valid_from, valid_to
        FROM core.channels
        """,
    ):
        chunks.append(_fmt("channel", **row))
    for row in _rows(
        con,
        """
        SELECT run_id, source, status, rows_read, rows_loaded, rows_rejected
        FROM core.ingest_runs
        ORDER BY started_at DESC
        LIMIT 20
        """,
    ):
        chunks.append(_fmt("ingest_run", **row))
    return chunks


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall((text or "").lower())


def _dot(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b[k] for k, v in a.items() if k in b)


def _norm(vec: dict[str, float]) -> float:
    return math.sqrt(sum(v * v for v in vec.values()))


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    if not tokens:
        return {}
    tf = Counter(tokens)
    n = len(tokens)
    return {t: (tf[t] / n) * idf[t] for t in tf if t in idf}


def retrieve(
    question: str, chunks: list[dict[str, Any]], *, k: int = DEFAULT_K
) -> list[dict[str, Any]]:
    """Top-k TF-IDF cosine. Rare tokens (SKUs, playbook) keep their weight."""
    if not chunks:
        return []
    docs = [tokenize(c["text"]) for c in chunks]
    df: Counter[str] = Counter()
    for toks in docs:
        df.update(set(toks))
    n = len(docs)
    idf = {t: math.log((n + 1) / (df[t] + 1)) + 1.0 for t in df}
    qvec = _tfidf_vector(tokenize(question), idf)
    qn = _norm(qvec)
    scored: list[tuple[float, dict[str, Any]]] = []
    for chunk, toks in zip(chunks, docs):
        dvec = _tfidf_vector(toks, idf)
        dn = _norm(dvec)
        if not qn or not dn:
            score = 0.0
        else:
            score = _dot(qvec, dvec) / (qn * dn)
        scored.append((score, chunk))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [chunk for score, chunk in scored[: max(1, k)] if score > 0]


def detect_concepts(text: str) -> set[str]:
    """Conservative markers from serialized k=v text, not NL paraphrases."""
    t = (text or "").lower()
    found: set[str] = set()
    if "sku=" in t or "kind=item " in t:
        found.add("item")
    if "listing_id=" in t:
        found.add("listing")
        found.add("listings")
    if "listing_age_days=" in t:
        found.add("listing_age")
    if "price_usd=" in t:
        found.add("asking_price")
    if "acquisition_cost" in t:
        found.add("acquisition_cost")
        found.add("capital_tied_up")
    if "watch_rate=" in t or "watchers=" in t or "views=" in t:
        found.add("engagement")
        found.add("watch_rate")
    if "offers=" in t:
        found.add("offers")
    if "kind=item_event" in t:
        found.add("item_history")
        found.add("events")
    if "kind=listing_event" in t:
        found.add("listing_as_of")
        found.add("events")
    if "kind=note" in t:
        found.add("retrieved_evidence")
    if "note_kind=playbook" in t:
        found.add("repricing_policy")
    if "kind=ingest_run" in t:
        found.add("warehouse_trust")
    if "status=owned" in t and "listing_id=" not in t:
        found.add("unlisted_owned")
    if "kind=order" in t:
        found.add("orders")
        found.add("channel_history")
    if "kind=channel" in t:
        found.add("channel_history")
    if "previous_snapshot" in t:
        found.add("previous_snapshot")
    return found


def _object_types(chunks: list[dict[str, Any]], sku: str | None) -> set[str]:
    types: set[str] = set()
    scoped = chunks
    if sku:
        needle = sku.lower()
        scoped = [c for c in chunks if needle in c["text"].lower()]
    kinds = {c["kind"] for c in scoped}
    if "item" in kinds or (sku and scoped):
        types.add("Item")
    if "listing" in kinds:
        types.add("Listing")
    if "channel" in kinds or any("platform=" in c["text"] for c in scoped):
        types.add("Channel")
    if "order" in kinds:
        types.add("Order")
    if "ingest_run" in kinds:
        types.add("IngestRun")
    return types


def score_lexical_case(chunks: list[dict[str, Any]], case: dict[str, Any]) -> dict[str, Any]:
    sku = case.get("sku")
    if sku:
        on_entity = [c for c in chunks if sku.lower() in c["text"].lower()]
    else:
        on_entity = list(chunks)
    present = detect_concepts("\n".join(c["text"] for c in on_entity))
    expected_missing = set(case.get("expected_missing") or [])
    required = set(case.get("required_concepts") or [])
    errors: list[str] = []
    for concept in required - expected_missing:
        if concept not in present:
            errors.append(f"retrieved text lacked {concept!r}")
    actual_missing = sorted(concept for concept in expected_missing if concept not in present)
    for concept in expected_missing:
        if concept in present:
            errors.append(f"lexical baseline invented {concept!r}")
    types = _object_types(chunks, sku)
    for needed in case.get("required_object_types") or []:
        if needed == "Recommendation":
            errors.append(f"missing object type {needed}")
            continue
        if needed not in types:
            errors.append(f"missing object type {needed}")
    return {
        "id": case["id"],
        "category": case.get("category"),
        "question": case["question"],
        "passed": not errors,
        "skipped": False,
        "errors": errors,
        "expected": {
            "sufficient": case.get("expected_sufficient"),
            "missing": case.get("expected_missing"),
            "object_types": case.get("required_object_types"),
        },
        "actual": {
            "missing": actual_missing,
            "object_types": sorted(types),
            "chunk_ids": [c["id"] for c in chunks],
        },
    }


def run_lexical_eval(con, *, k: int = DEFAULT_K, questions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    from evals.context_questions import QUESTIONS

    catalog = questions if questions is not None else QUESTIONS
    corpus = build_corpus(con)
    results = []
    for case in catalog:
        hits = retrieve(case["question"], corpus, k=k)
        results.append(score_lexical_case(hits, case))
    passed = sum(1 for r in results if r["passed"])
    failed = [r for r in results if not r["passed"]]
    skipped = [r for r in results if r["skipped"]]
    return {
        "total": len(catalog),
        "passed": passed,
        "failed": len(failed),
        "skipped": len(skipped),
        "ok": not failed,
        "k": k,
        "corpus_size": len(corpus),
        "cases": results,
    }


# Back-compat aliases while callers migrate off the RAG name.
run_rag_eval = run_lexical_eval
score_rag_case = score_lexical_case
