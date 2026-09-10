"""Honest RAG baseline vs the gold context-assembly catalog.

RAG is a comparison, not the architecture. These tests lock two properties:
the retriever is not sabotaged on unstructured notes, and it does not get
credit for inventing a listing on an unlisted item.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdp_cli import db
from cdp_cli.ingest import ALL_JOBS
from evals.context_questions import QUESTIONS
from evals.rag_baseline import build_corpus, retrieve, run_rag_eval
from evals.run import run_compare, run_eval


def _build(con):
    for job in ALL_JOBS:
        job(con, db.data_dir()).run()


def test_corpus_serializes_notes_and_listings_not_recommendations(warehouse):
    _build(warehouse)
    chunks = build_corpus(warehouse)
    kinds = {c["kind"] for c in chunks}
    assert "note" in kinds
    assert "listing" in kinds
    assert "item" in kinds
    assert "attention" not in kinds
    assert any("stone-cargo-l" in c["text"] for c in chunks if c["kind"] == "note")
    assert not any(
        c["kind"] == "listing" and "stone-cargo-l" in c["text"] for c in chunks
    )


def test_rag_retrieves_seller_note_for_hybrid_question(warehouse):
    _build(warehouse)
    chunks = build_corpus(warehouse)
    hits = retrieve("What do seller notes say about stone-cargo-l?", chunks, k=8)
    joined = " ".join(h["text"] for h in hits).lower()
    assert "stone-cargo-l" in joined
    assert "oil mark" in joined or "studio" in joined


def test_rag_does_not_invent_listing_for_unlisted_sku(warehouse):
    _build(warehouse)
    report = run_rag_eval(warehouse)
    q03 = next(c for c in report["cases"] if c["id"] == "Q03")
    assert q03["passed"] is True
    assert "listing" in q03["actual"]["missing"]


def test_compare_covers_every_gold_id_and_engine_still_passes(warehouse):
    _build(warehouse)
    engine = run_eval(warehouse)
    assert engine["passed"] == engine["total"] == 20
    compare = run_compare(warehouse)
    ids = [c["id"] for c in compare["cases"]]
    assert ids == [q["id"] for q in QUESTIONS]
    assert compare["engine"]["passed"] == 20
    assert compare["engine"]["failed"] == 0
    by_cat = compare["by_category"]
    assert "hybrid" in by_cat
    assert "insufficient" in by_cat
    assert "multi_hop" in by_cat


def test_hybrid_notes_are_not_sabotaged(warehouse):
    _build(warehouse)
    report = run_rag_eval(warehouse)
    hybrid = [c for c in report["cases"] if c["category"] == "hybrid"]
    assert hybrid
    assert all(c["passed"] for c in hybrid)


def test_engine_wins_insufficient_disclosure(warehouse):
    _build(warehouse)
    compare = run_compare(warehouse)
    q03 = next(c for c in compare["cases"] if c["id"] == "Q03")
    q08 = next(c for c in compare["cases"] if c["id"] == "Q08")
    assert q03["engine"] is True
    assert q08["engine"] is True
    assert q03["winner"] in {"tie", "engine"}
    assert q08["winner"] in {"tie", "engine"}
