"""Policy refs are control logic, not warehouse rows."""
from __future__ import annotations

from cdp_cli import db
from cdp_cli.core.engine import assemble_context
from cdp_cli.ingest import ALL_JOBS
from cdp_cli.policy import CATEGORIES, POLICIES, PRICE_RECOMMENDATIONS


def _build(con):
    for job in ALL_JOBS:
        job(con, db.data_dir()).run()


def test_policy_categories_are_named() -> None:
    assert CATEGORIES == (
        "data_contract",
        "context",
        "decision",
        "action",
        "security",
    )
    cats = {p.category for p in POLICIES}
    assert cats == set(CATEGORIES)
    assert PRICE_RECOMMENDATIONS == {
        "REVIEW_PRICE",
        "KEEP_PRICE",
        "INSUFFICIENT_EVIDENCE",
    }


def test_reprice_bundle_exposes_price_review_policy(warehouse) -> None:
    _build(warehouse)
    bundle = assemble_context(
        warehouse, question="Should I reprice j4-military-s?"
    )
    ids = {p["id"] for p in bundle.applicable_policies}
    assert "resale.decision.price-review" in ids
    assert "resale.action.human-approval" in ids
    assert bundle.provenance.get("policy_ids")
    rules = [r.get("name") for r in bundle.applicable_rules]
    assert "price_review" in rules
    blob = json_blob(bundle)
    assert "0.89" not in blob
    assert "* 0.89" not in blob


def json_blob(bundle) -> str:
    import json

    return json.dumps(bundle.to_dict(), default=str)
