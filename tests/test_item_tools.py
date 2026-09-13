"""Typed item object tools — current state + history."""
from __future__ import annotations

import pytest

from cdp_cli import db
from cdp_cli.domains.resale.services import get_item, get_item_history
from cdp_cli.ingest import ALL_JOBS


def _build(con):
    for j in ALL_JOBS:
        j(con, db.data_dir()).run()


def test_get_item_unlisted_has_no_listings(warehouse):
    _build(warehouse)
    payload = get_item(warehouse, "stone-cargo-l")
    assert payload.kind == "fact"
    item = payload.data["item"]
    assert item["sku"] == "stone-cargo-l"
    assert item["status"] == "owned"
    assert item["acquisition_cost_cny"] == 3943
    assert item["acquired_at"] is not None
    assert item["inventory_age_days"] is not None
    assert payload.data["listings"] == []
    assert payload.data["orders"] == []
    assert payload.data["listing_count"] == 0
    assert "get_item" == payload.provenance.tool


def test_get_item_listed_includes_channel_and_engagement(warehouse):
    _build(warehouse)
    payload = get_item(warehouse, "j4-military-s")
    item = payload.data["item"]
    assert item["status"] == "listed"
    listings = payload.data["listings"]
    assert len(listings) == 1
    listing = listings[0]
    assert listing["platform"] == "grailed"
    assert listing["status"] == "active"
    assert listing["price_usd"] is not None
    assert payload.data["orders"] == []


def test_get_item_sold_includes_order(warehouse):
    _build(warehouse)
    payload = get_item(warehouse, "j1-panda-m")
    assert payload.data["item"]["status"] == "sold"
    assert payload.data["order_count"] >= 1
    assert payload.data["orders"][0]["revenue_usd"] > 0


def test_get_item_unknown_sku(warehouse):
    _build(warehouse)
    with pytest.raises(KeyError, match="unknown item"):
        get_item(warehouse, "no-such-sku")


def test_get_item_empty_sku(warehouse):
    with pytest.raises(ValueError, match="sku is required"):
        get_item(warehouse, "  ")


def test_get_item_history_timeline_is_ordered(warehouse):
    _build(warehouse)
    payload = get_item_history(warehouse, "j4-military-s")
    assert payload.kind == "fact"
    types = [row["type"] for row in payload.data["timeline"]]
    assert "ordered" in types
    assert "received" in types
    assert "listing_opened" in types
    stamps = [row["at"] for row in payload.data["timeline"] if row["at"]]
    assert stamps == sorted(stamps)
    for row in payload.data["timeline"]:
        assert row["source"] in {
            "catalog.item_events",
            "sales.listings",
            "sales.listing_events",
            "sales.orders",
        }


def test_get_item_history_unlisted_has_supply_events_only(warehouse):
    _build(warehouse)
    payload = get_item_history(warehouse, "stone-cargo-l")
    types = {row["type"] for row in payload.data["timeline"]}
    assert "ordered" in types
    assert "listing_opened" not in types
    assert payload.data["engagement"] == []
    assert payload.data["orders"] == []
