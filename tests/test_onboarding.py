"""Onboarding agent: profile, propose, never ingest."""
from __future__ import annotations

import json
from pathlib import Path

from cdp_cli.onboard import profile_file, propose_file, review_proposal

FIXTURES = Path(__file__).parent / "fixtures" / "onboard"


def test_profiler_reads_public_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "items.jsonl"
    path.write_text(
        json.dumps(
            {
                "sku": "demo-sku-1",
                "product": "Canvas Tote",
                "acquisition_cost_cny": 120,
                "status": "owned",
            }
        )
        + "\n"
        + json.dumps(
            {
                "sku": "demo-sku-2",
                "product": "Work Shirt",
                "acquisition_cost_cny": None,
                "status": "listed",
            }
        )
        + "\n"
    )
    report = profile_file(path)
    names = {f["name"] for f in report["fields"]}
    assert names == {"sku", "product", "acquisition_cost_cny", "status"}
    assert report["row_count"] == 2
    sku = next(f for f in report["fields"] if f["name"] == "sku")
    assert sku["unique"] is True
    cost = next(f for f in report["fields"] if f["name"] == "acquisition_cost_cny")
    assert cost["null_count"] == 1


def test_ambiguous_fields_become_human_questions(tmp_path: Path) -> None:
    path = tmp_path / "mystery.csv"
    path.write_text("id,amount,date,notes\n1,12.5,2026-01-01,hello\n2,8,2026-01-02,x\n")
    proposal = propose_file(path)
    assert proposal["status"] == "PROPOSED"
    assert "amount" in proposal["ambiguous_fields"] or any(
        "amount" in q for q in proposal["human_questions"]
    )
    assert proposal["human_questions"]
    assert "ingest" in proposal["approval"].lower() or "human" in proposal["approval"].lower()
    mapped_targets = {m["target_field"] for m in proposal["field_mappings"]}
    assert "price_usd" not in mapped_targets


def test_review_does_not_approve(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"status": "PROPOSED", "source_name": "x", "source_type": "csv"}))
    reviewed = review_proposal(path)
    assert reviewed["status"] == "PROPOSED"
    assert "does not activate" in reviewed["review_note"].lower() or "human" in reviewed["review_note"].lower()
    assert "deterministic" in reviewed["canonical_ingest"].lower()
