"""recent_changes diffs a prior as-of snapshot instead of always abstaining."""
from __future__ import annotations

from datetime import timedelta

from cdp_cli import db
from cdp_cli.business import (
    capture_business_snapshot,
    get_business_snapshot,
    list_business_snapshots,
)
from cdp_cli.clock import reference_now
from cdp_cli.core import assemble_context
from cdp_cli.ingest import ALL_JOBS
from cdp_cli.metrics import STALE_LISTING_DAYS


def _build(con):
    for job in ALL_JOBS:
        job(con, db.data_dir()).run()


def test_empty_warehouse_still_names_missing_previous_snapshot(warehouse):
    bundle = assemble_context(
        warehouse,
        question="What materially changed since the previous business snapshot?",
        intent="recent_changes",
    )
    assert bundle.sufficient is False
    assert {m.concept for m in bundle.missing_context} == {"previous_snapshot"}
    assert bundle.facts.get("previous_snapshot") in (None, {})


def test_seeded_world_reconstructs_previous_snapshot_and_deltas(warehouse):
    _build(warehouse)
    bundle = assemble_context(
        warehouse,
        question="What materially changed since the previous business snapshot?",
        intent="recent_changes",
    )
    assert bundle.intent == "recent_changes"
    assert bundle.sufficient is True
    assert bundle.missing_context == []
    assert "previous_snapshot" in bundle.facts
    types = {obj.type for obj in bundle.objects}
    assert "BusinessSnapshot" in types
    ids = {obj.id for obj in bundle.objects if obj.type == "BusinessSnapshot"}
    assert "previous" in ids
    assert "current" in ids
    deltas = bundle.facts["deltas"]
    assert deltas
    # Demo world listed several items inside the default lookback; a zero
    # delta would mean we compared the same instant to itself.
    assert any(row["delta"] != 0 for row in deltas.values())
    prev = bundle.facts["previous_snapshot"]
    curr = bundle.facts["current_snapshot"]
    assert prev["active_listings"] < curr["active_listings"]
    assert prev["as_of"] != curr["as_of"]


def test_as_of_snapshot_uses_listing_history_not_current_projection(warehouse):
    _build(warehouse)
    now = reference_now()
    current = get_business_snapshot(warehouse).data
    prior = get_business_snapshot(
        warehouse, as_of=now - timedelta(days=STALE_LISTING_DAYS)
    ).data
    assert prior["active_listings"] < current["active_listings"]
    assert prior["sold_items"] < current["sold_items"]
    assert prior["items_total"] <= current["items_total"]


def test_capture_persists_checkpoint_without_changing_live_query(warehouse):
    _build(warehouse)
    first = capture_business_snapshot(warehouse, trigger="test")
    rows = list_business_snapshots(warehouse)
    assert len(rows) == 1
    assert rows[0]["snapshot_id"] == first["snapshot_id"]
    assert rows[0]["payload"]["items_total"] == get_business_snapshot(warehouse).data["items_total"]
