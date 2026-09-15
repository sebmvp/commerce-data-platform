"""Note/policy retrieval evaluation.

Compares whole-query ILIKE (historical production) against PostgreSQL
full-text search. This is not the TF-IDF lexical baseline in
evals/lexical_baseline.py — that serializes warehouse rows for
assemble_context comparison.

Rank/score is a retrieval ordering signal, not model confidence.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from evals.retrieval_questions import CASES

DEFAULT_K = 5
Retrievers = dict[str, Callable[..., list[dict[str, Any]]]]


def _rows(con, sql: str, params: list | None = None) -> list[dict[str, Any]]:
    rel = con.execute(sql, params or [])
    cols = [c[0] for c in rel.description]
    return [dict(zip(cols, row, strict=False)) for row in rel.fetchall()]


def retrieve_ilike(
    con,
    *,
    question: str,
    object_id: str | None = None,
    kind: str | None = None,
    k: int = DEFAULT_K,
) -> list[dict[str, Any]]:
    """Historical production: whole-query ILIKE on title/body."""
    clauses: list[str] = []
    params: list[Any] = []
    if object_id:
        clauses.append("object_id = ?")
        params.append(object_id)
    if kind:
        clauses.append("kind = ?")
        params.append(kind)
    q = (question or "").strip()
    if q:
        needle = f"%{q}%"
        clauses.append("(body ILIKE ? OR coalesce(title, '') ILIKE ?)")
        params.extend([needle, needle])
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT note_id, kind, object_type, object_id, title, body, "
        "NULL::float AS rank, body AS excerpt "
        f"FROM ops.notes{where} ORDER BY created_at DESC LIMIT ?"
    )
    params.append(max(1, min(int(k), 50)))
    return _rows(con, sql, params)


def _or_tsquery(con, question: str) -> str | None:
    """Stemmed OR query. AND of every token fails ordinary questions
    that include verbs like 'say' / 'recommend' absent from the note."""
    q = (question or "").strip()
    if not q:
        return None
    row = con.execute(
        "SELECT NULLIF(replace(plainto_tsquery('english', ?)::text, ' & ', ' | '), '')",
        [q],
    ).fetchone()
    if row and row[0]:
        return str(row[0])
    return None


def retrieve_fts(
    con,
    *,
    question: str,
    object_id: str | None = None,
    kind: str | None = None,
    k: int = DEFAULT_K,
) -> list[dict[str, Any]]:
    """PostgreSQL FTS over title (A) + body (B). Uses search_tsv when present."""
    clauses: list[str] = []
    params: list[Any] = []
    if object_id:
        clauses.append("n.object_id = ?")
        params.append(object_id)
    if kind:
        clauses.append("n.kind = ?")
        params.append(kind)
    tsq = _or_tsquery(con, question)
    has_tsv = (
        con.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'ops' AND table_name = 'notes'
              AND column_name = 'search_tsv'
            """
        ).fetchone()
        is not None
    )
    vec = (
        "n.search_tsv"
        if has_tsv
        else (
            "setweight(to_tsvector('english', coalesce(n.title, '')), 'A') || "
            "setweight(to_tsvector('english', coalesce(n.body, '')), 'B')"
        )
    )
    if tsq:
        clauses.append(f"{vec} @@ tsq")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT n.note_id, n.kind, n.object_type, n.object_id, n.title, n.body,
                   ts_rank_cd({vec}, tsq) AS rank,
                   ts_headline(
                     'english', n.body, tsq,
                     'MaxWords=24, MinWords=8, MaxFragments=1'
                   ) AS excerpt
            FROM ops.notes n,
                 CAST(? AS tsquery) AS tsq
            {where}
            ORDER BY rank DESC NULLS LAST, n.created_at DESC
            LIMIT ?
        """
        params = [tsq, *params, max(1, min(int(k), 50))]
        return _rows(con, sql, params)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT n.note_id, n.kind, n.object_type, n.object_id, n.title, n.body, "
        "NULL::float AS rank, n.body AS excerpt "
        f"FROM ops.notes n{where} ORDER BY n.created_at DESC LIMIT ?"
    )
    params.append(max(1, min(int(k), 50)))
    return _rows(con, sql, params)


def retrieve_production(con, **kwargs: Any) -> list[dict[str, Any]]:
    from cdp_cli.domains.resale.services.items import search_notes

    hits = search_notes(
        con,
        object_id=kwargs.get("object_id"),
        query=kwargs.get("question") or None,
        kind=kwargs.get("kind"),
        limit=kwargs.get("k", DEFAULT_K),
    )
    return hits


def _score_case(
    case: dict[str, Any],
    hits: list[dict[str, Any]],
) -> dict[str, Any]:
    expected = list(case.get("expected_note_ids") or [])
    unexpected = set(case.get("unexpected_note_ids") or [])
    got = [str(h.get("note_id")) for h in hits if h.get("note_id")]
    got_set = set(got)
    expect_empty = bool(case.get("expect_empty") or not expected)
    errors: list[str] = []
    if expect_empty:
        if got:
            errors.append(f"expected no notes, got {got}")
        recall = 1.0 if not got else 0.0
        precision = 1.0 if not got else 0.0
        mrr = 1.0 if not got else 0.0
        first_rank = None
    else:
        found = [nid for nid in expected if nid in got_set]
        recall = len(found) / len(expected) if expected else 1.0
        precision = (
            len(got_set & set(expected)) / len(got_set) if got_set else 0.0
        )
        first_rank = None
        for i, nid in enumerate(got, start=1):
            if nid in expected:
                first_rank = i
                break
        mrr = 0.0 if first_rank is None else 1.0 / first_rank
        missing = [nid for nid in expected if nid not in got_set]
        if missing:
            errors.append(f"missing {missing}")
    leaked = sorted(got_set & unexpected)
    if leaked:
        errors.append(f"unexpected {leaked}")
    return {
        "id": case["id"],
        "question": case.get("question") or "",
        "object_id": case.get("object_id"),
        "kind": case.get("kind"),
        "tags": case.get("tags") or [],
        "semantic_paraphrase": bool(case.get("semantic_paraphrase")),
        "passed": not errors,
        "errors": errors,
        "expected": expected,
        "got": got,
        "recall": recall,
        "precision": precision,
        "mrr": mrr,
        "first_rank": first_rank,
    }


def _aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(cases)
    lexical = [c for c in cases if not c.get("semantic_paraphrase")]
    semantic_misses = [
        c
        for c in cases
        if c.get("semantic_paraphrase") and not c["passed"]
    ]
    return {
        "total": n,
        "passed": sum(1 for c in cases if c["passed"]),
        "failed": sum(1 for c in cases if not c["passed"]),
        "macro_recall": sum(c["recall"] for c in cases) / n if n else 0.0,
        "macro_precision": sum(c["precision"] for c in cases) / n if n else 0.0,
        "macro_mrr": sum(c["mrr"] for c in cases) / n if n else 0.0,
        "lexical_total": len(lexical),
        "lexical_passed": sum(1 for c in lexical if c["passed"]),
        "semantic_failures": [c["id"] for c in semantic_misses],
        "ok": all(c["passed"] for c in lexical),
        "cases": cases,
    }


def run_retriever(
    con,
    retrieve: Callable[..., list[dict[str, Any]]],
    *,
    k: int = DEFAULT_K,
) -> dict[str, Any]:
    scored = []
    for case in CASES:
        hits = retrieve(
            con,
            question=case.get("question") or "",
            object_id=case.get("object_id"),
            kind=case.get("kind"),
            k=k,
        )
        scored.append(_score_case(case, hits))
    return _aggregate(scored)


def run_retrieval_eval(con, *, k: int = DEFAULT_K) -> dict[str, Any]:
    ilike = run_retriever(con, retrieve_ilike, k=k)
    fts = run_retriever(con, retrieve_fts, k=k)
    production = run_retriever(con, retrieve_production, k=k)
    return {
        "layer": "note_retrieval",
        "k": k,
        "ilike": {
            "passed": ilike["passed"],
            "total": ilike["total"],
            "failed": ilike["failed"],
            "macro_recall": round(ilike["macro_recall"], 4),
            "macro_precision": round(ilike["macro_precision"], 4),
            "macro_mrr": round(ilike["macro_mrr"], 4),
            "lexical_passed": ilike["lexical_passed"],
            "lexical_total": ilike["lexical_total"],
            "semantic_failures": ilike["semantic_failures"],
            "ok": ilike["ok"],
            "cases": ilike["cases"],
        },
        "fts": {
            "passed": fts["passed"],
            "total": fts["total"],
            "failed": fts["failed"],
            "macro_recall": round(fts["macro_recall"], 4),
            "macro_precision": round(fts["macro_precision"], 4),
            "macro_mrr": round(fts["macro_mrr"], 4),
            "lexical_passed": fts["lexical_passed"],
            "lexical_total": fts["lexical_total"],
            "semantic_failures": fts["semantic_failures"],
            "ok": fts["ok"],
            "cases": fts["cases"],
        },
        "production": {
            "passed": production["passed"],
            "total": production["total"],
            "failed": production["failed"],
            "macro_recall": round(production["macro_recall"], 4),
            "macro_precision": round(production["macro_precision"], 4),
            "ok": production["ok"],
        },
        "ok": fts["ok"],
    }
