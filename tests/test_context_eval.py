"""Run implemented context-assembly eval questions against sample data."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdp_cli import db
from cdp_cli.core import assemble_context
from cdp_cli.ingest import ALL_JOBS
from evals.context_questions import QUESTIONS


def _build(con):
    for job in ALL_JOBS:
        job(con, db.data_dir()).run()


def test_eval_catalog_has_stable_ids():
    ids = [q["id"] for q in QUESTIONS]
    assert len(ids) == len(set(ids))
    assert len(QUESTIONS) >= 12
    categories = {q["category"] for q in QUESTIONS}
    for needed in (
        "hybrid",
        "simple_fact",
        "temporal",
        "multi_hop",
        "computed",
        "change",
        "diagnosis",
        "data_quality",
        "insufficient",
        "action",
    ):
        assert needed in categories


@pytest.mark.parametrize("case", QUESTIONS, ids=lambda c: c["id"])
def test_gold_eval_case(warehouse, case):
    _build(warehouse)
    bundle = assemble_context(
        warehouse,
        question=case["question"],
        intent=case["intent"],
        sku=case["sku"],
    )
    assert bundle.intent == case["intent"]
    assert bundle.sufficient is case["expected_sufficient"]
    missing = {m.concept for m in bundle.missing_context}
    for concept in case["expected_missing"]:
        assert concept in missing
    types = {obj.type for obj in bundle.objects}
    for needed in case["required_object_types"]:
        assert needed in types
    if case["expected_sufficient"]:
        assert bundle.missing_context == []


def test_eval_catalog_has_twenty_questions():
    ids = [q["id"] for q in QUESTIONS]
    assert len(ids) == len(set(ids))
    assert len(QUESTIONS) == 20
