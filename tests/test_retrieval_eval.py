"""Retrieval gold evaluation: ilike vs PostgreSQL FTS vs production search_notes."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdp_cli import db
from cdp_cli.ingest import ALL_JOBS
from evals.retrieval_eval import (
    retrieve_fts,
    retrieve_ilike,
    retrieve_production,
    run_retriever,
)


def _build(con):
    for job in ALL_JOBS:
        job(con, db.data_dir()).run()


def test_fts_dominates_ilike_on_gold_retrieval_set(warehouse):
    _build(warehouse)
    ilike = run_retriever(warehouse, retrieve_ilike)
    fts = run_retriever(warehouse, retrieve_fts)
    assert fts["macro_recall"] >= ilike["macro_recall"]
    assert fts["macro_mrr"] >= ilike["macro_mrr"]
    assert fts["lexical_passed"] >= 18, fts["lexical_passed"]
    assert [c["id"] for c in fts["cases"] if not c["passed"]] == ["R15"]


def test_production_search_uses_fts_and_matches_eval(warehouse):
    _build(warehouse)
    prod = run_retriever(warehouse, retrieve_production)
    fts = run_retriever(warehouse, retrieve_fts)
    assert prod["macro_recall"] == fts["macro_recall"]
    assert prod["macro_mrr"] == fts["macro_mrr"]
    assert [c["id"] for c in prod["cases"] if not c["passed"]] == ["R15"]


def test_production_returns_typed_evidence(warehouse):
    _build(warehouse)
    hits = retrieve_production(
        warehouse, question="What does the Grailed seller fee policy say?"
    )
    hit = hits[0]
    for field in ("note_id", "kind", "title", "body", "excerpt", "rank", "object_type", "object_id"):
        assert field in hit
    assert hit["note_id"] == "policy-grailed-fees"
    assert "seller" in hit["excerpt"].lower()


def test_rank_is_retrieval_ordering_not_confidence(warehouse):
    _build(warehouse)
    hits = retrieve_production(warehouse, question="stale listing playbook")
    ranks = [h["rank"] for h in hits]
    assert ranks[0] == max(ranks)
    assert ranks == sorted(ranks, reverse=True)


def test_object_scope_stays_deterministic_despite_ranking(warehouse):
    _build(warehouse)
    hits = retrieve_production(warehouse, object_id="j4-military-s")
    assert [h["note_id"] for h in hits] == ["note-j4-military-wear"]


def test_semantic_gate_case_is_named_for_sebastian(warehouse):
    """R15 shares no lexeme with the expected note: vector-search gate."""
    from evals.retrieval_questions import CASES

    r15 = next(c for c in CASES if c["id"] == "R15")
    assert r15.get("semantic_paraphrase") is True


def test_alembic_heads_notes_fts(warehouse):
    from alembic.config import Config

    from alembic import command

    url = os.environ.get("CDP_DATABASE_URL", "").replace(
        "postgresql://", "postgresql+psycopg://", 1
    )
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    row = warehouse.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='ops' AND table_name='notes'
          AND column_name='search_tsv'
        """
    ).fetchone()
    assert row is not None
