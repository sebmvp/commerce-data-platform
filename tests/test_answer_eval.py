"""Grounded-answer eval on gold ids. Scores the copilot contract, not an LLM judge."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdp_cli import db
from cdp_cli.ingest import ALL_JOBS
from cdp_cli.llm import FakeProvider, ground_answer
from evals.answer_eval import run_answer_eval, score_answer_case
from evals.context_questions import QUESTIONS


def _build(con):
    for job in ALL_JOBS:
        job(con, db.data_dir()).run()


def test_fake_provider_restates_bundle_values(warehouse):
    _build(warehouse)
    result = ground_answer(
        warehouse, question="Should I reprice j4-military-s?"
    )
    assert result["grounding_status"] == "grounded"
    assert result["provider"] == "fake"
    assert "Grounded on the assembled ContextBundle" not in result["answer"]
    assert "j4-military-s" in result["answer"]
    catalog = result["bundle"]["evidence_catalog"]
    assert result["evidence_refs"]
    assert all(ref in catalog for ref in result["evidence_refs"])
    assert any(ref.startswith("object:Item:") for ref in result["evidence_refs"])
    facts = result["bundle"].get("facts") or {}
    metrics = result["bundle"].get("metrics") or {}
    needles: list[str] = []
    for value in list(facts.values()) + list(metrics.values()):
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            needles.append(str(value))
        elif isinstance(value, str) and value:
            needles.append(value)
    assert needles, "reprice bundle should expose scalar facts or metrics"
    assert any(needle in result["answer"] for needle in needles)


def test_insufficient_gold_case_abstains_without_citations(warehouse):
    _build(warehouse)
    case = next(q for q in QUESTIONS if q["id"] == "Q03")
    result = ground_answer(
        warehouse,
        question=case["question"],
        intent=case["intent"],
        sku=case["sku"],
    )
    scored = score_answer_case(result, case)
    assert scored["passed"], scored["errors"]
    assert result["abstained"] is True
    assert result["grounding_status"] == "abstained"


@pytest.mark.parametrize("case", QUESTIONS, ids=lambda c: c["id"])
def test_gold_answer_eval_case(warehouse, case):
    _build(warehouse)
    result = ground_answer(
        warehouse,
        question=case["question"],
        intent=case.get("intent"),
        sku=case.get("sku"),
        provider=FakeProvider(),
    )
    scored = score_answer_case(result, case)
    assert scored["passed"], scored["errors"]


def test_answer_eval_suite_is_twenty_of_twenty(warehouse):
    _build(warehouse)
    warehouse.close()
    con = db.connect(read_only=True)
    try:
        report = run_answer_eval(con)
    finally:
        con.close()
    assert report["total"] == 20
    assert report["passed"] == 20
    assert report["failed"] == 0
    assert report["ok"] is True
    assert report["layer"] == "grounded_answers"
    assert report["provider"] == "fake"
