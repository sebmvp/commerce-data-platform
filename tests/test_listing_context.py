"""Listing as-of, channel comparison, and listing-performance context."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cdp_cli import db
from cdp_cli.business import (
    get_channel_comparison,
    get_listing_as_of,
    get_listing_performance,
)
from cdp_cli.context import assemble_context
from cdp_cli.ingest import ALL_JOBS


def _build(con):
    for job in ALL_JOBS:
        job(con, db.data_dir()).run()


def test_listing_as_of_two_weeks_ago_is_covered(warehouse):
    _build(warehouse)
    at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=14)
    payload = get_listing_as_of(warehouse, "j4-military-s", as_of=at)
    assert payload.data["covered"] is True
    assert payload.data["listings"]
    assert payload.data["listings"][0]["platform"] == "grailed"

    bundle = assemble_context(
        warehouse,
        question="What was the active listing state for j4-military-s two weeks ago?",
    )
    assert bundle.intent == "listing_as_of"
    assert bundle.sufficient is True
    assert "listing_as_of" in bundle.facts
    assert bundle.facts["listing_as_of"]["covered"] is True


def test_channel_comparison_has_history_and_unlisted_capital(warehouse):
    _build(warehouse)
    payload = get_channel_comparison(warehouse)
    platforms = {row["platform"] for row in payload.data["channels"]}
    assert "grailed" in platforms
    assert payload.data["unlisted_owned"]
    assert payload.data["capital_tied_up_cny"] > 0

    bundle = assemble_context(
        warehouse,
        question=(
            "Which owned items have capital tied up, no active listing, "
            "and have historically performed better on one channel than another?"
        ),
    )
    assert bundle.intent == "compare_channels"
    assert bundle.sufficient is True
    types = {obj.type for obj in bundle.objects}
    assert "Channel" in types
    assert "Item" in types


def test_listing_performance_flags_attention_without_offers(warehouse):
    _build(warehouse)
    payload = get_listing_performance(warehouse)
    flagged = payload.data.get("high_attention_no_offers") or []
    assert flagged, "expected at least one high-attention / zero-offer listing"

    bundle = assemble_context(
        warehouse,
        question="Which listings have strong attention but weak offer conversion?",
    )
    assert bundle.intent == "listing_performance"
    assert bundle.sufficient is True
    assert "watch_rate" in bundle.facts or "listings" in bundle.facts
