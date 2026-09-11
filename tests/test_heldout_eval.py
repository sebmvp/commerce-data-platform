"""Held-out scenario validation against World B."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from cdp_cli import db
from cdp_cli.core import assemble_context
from cdp_cli.ingest import ALL_JOBS
from evals.heldout_questions import HELD_OUT
from evals.run import run_eval

HELDOUT = Path(__file__).resolve().parents[1] / "sample_data_heldout"


@pytest.fixture()
def heldout_warehouse(monkeypatch):
    url = os.environ.get("CDP_TEST_DATABASE_URL", db.TEST_URL)
    monkeypatch.setenv("CDP_DATABASE_URL", url)
    monkeypatch.setenv("CDP_DATA", str(HELDOUT))
    monkeypatch.delenv("CDP_AS_OF", raising=False)
    db.ensure_database(url)
    con = db.connect()
    db.reset_schema(con)
    yield con
    con.close()


def _build(con):
    for job in ALL_JOBS:
        job(con, db.data_dir()).run()


def test_heldout_world_exists():
    assert (HELDOUT / "world.json").exists()
    assert (HELDOUT / "catalog_items.jsonl").exists()
    text = (HELDOUT / "catalog_items.jsonl").read_text()
    assert "j4-military-s" not in text
    assert "merino-crew-m" in text


def test_heldout_catalog_ids_are_stable():
    ids = [q["id"] for q in HELD_OUT]
    assert len(ids) == len(set(ids))
    assert ids == [f"H{i:02d}" for i in range(1, len(HELD_OUT) + 1)]


@pytest.mark.skipif(not (HELDOUT / "catalog_items.jsonl").exists(), reason="held-out world missing")
@pytest.mark.parametrize("case", HELD_OUT, ids=lambda c: c["id"])
def test_heldout_eval_case(heldout_warehouse, case):
    _build(heldout_warehouse)
    bundle = assemble_context(
        heldout_warehouse,
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


@pytest.mark.skipif(not (HELDOUT / "catalog_items.jsonl").exists(), reason="held-out world missing")
def test_heldout_suite_reports_full_denominator(heldout_warehouse):
    _build(heldout_warehouse)
    report = run_eval(heldout_warehouse, suite="heldout")
    assert report["suite"] == "HELD OUT"
    assert report["total"] == len(HELD_OUT)
    assert report["passed"] + report["failed"] + report["skipped"] == report["total"]
    assert report["ok"]
