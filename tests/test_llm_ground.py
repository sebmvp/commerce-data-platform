"""Grounded answers over a ContextBundle. The model is not the database."""
from __future__ import annotations

from cdp_cli import db
from cdp_cli.ingest import ALL_JOBS
from cdp_cli.llm import ground_answer


def _build(con):
    for job in ALL_JOBS:
        job(con, db.data_dir()).run()


def test_insufficient_bundle_abstains(warehouse):
    _build(warehouse)
    result = ground_answer(
        warehouse, question="Should I reprice stone-cargo-l?"
    )
    assert result["abstained"] is True
    assert result["bundle"]["sufficient"] is False
    assert "listing" in " ".join(
        m["concept"] for m in result["bundle"]["missing_context"]
    )
    assert "ABSTAIN" in result["answer"].upper() or "missing" in result["answer"].lower()
    assert result["provider"] == "fake"


def test_sufficient_bundle_answers_with_evidence(warehouse):
    _build(warehouse)
    result = ground_answer(
        warehouse, question="Should I reprice j4-military-s?"
    )
    assert result["abstained"] is False
    assert result["bundle"]["sufficient"] is True
    assert "j4-military-s" in result["answer"]
    assert result["evidence"]
    assert result["provider"] == "fake"
