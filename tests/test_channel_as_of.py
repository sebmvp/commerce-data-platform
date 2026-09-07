"""SCD-2 channel as-of: half-open intervals and point-in-time lookup."""
from __future__ import annotations

import json

import pytest

from cdp_cli import db
from cdp_cli.business import get_channel_as_of, get_item
from cdp_cli.ingest import ALL_JOBS
from cdp_cli.ingest.catalog import ChannelIngest, ItemIngest
from cdp_cli.ingest.sales import ListingIngest


def _build(con):
    for j in ALL_JOBS:
        j(con, db.data_dir()).run()


def test_closed_grailed_version_ends_at_successor_valid_from(warehouse):
    _build(warehouse)
    rows = warehouse.execute(
        """
        SELECT fee_pct, valid_from, valid_to
        FROM core.channels
        WHERE platform = 'grailed'
        ORDER BY valid_from
        """
    ).fetchall()
    assert len(rows) == 2
    assert rows[0][0] == pytest.approx(0.09)
    assert rows[1][0] == pytest.approx(0.12)
    assert rows[0][2] == rows[1][1]
    assert rows[1][2] is None


def test_channel_versions_do_not_overlap(warehouse):
    _build(warehouse)
    overlaps = warehouse.execute(
        """
        SELECT a.channel_key, b.channel_key
        FROM core.channels a
        JOIN core.channels b
          ON a.platform = b.platform
         AND a.handle = b.handle
         AND a.channel_key < b.channel_key
         AND a.valid_from < coalesce(b.valid_to, TIMESTAMP '9999-12-31')
         AND b.valid_from < coalesce(a.valid_to, TIMESTAMP '9999-12-31')
        """
    ).fetchall()
    assert overlaps == []


def test_grailed_as_of_before_fee_change_is_nine_percent(warehouse):
    _build(warehouse)
    payload = get_channel_as_of(warehouse, "grailed", as_of="2025-06-01T00:00:00")
    assert payload.kind == "fact"
    assert payload.provenance.tool == "get_channel_as_of"
    versions = payload.data["versions"]
    assert len(versions) == 1
    assert versions[0]["fee_pct"] == pytest.approx(0.09)
    assert payload.data["interval"] == "[valid_from, valid_to)"


def test_grailed_as_of_on_fee_change_boundary_is_twelve_percent(warehouse):
    _build(warehouse)
    payload = get_channel_as_of(warehouse, "grailed", as_of="2026-01-01T00:00:00")
    versions = payload.data["versions"]
    assert len(versions) == 1
    assert versions[0]["fee_pct"] == pytest.approx(0.12)


def test_grailed_as_of_after_fee_change_is_twelve_percent(warehouse):
    _build(warehouse)
    payload = get_channel_as_of(warehouse, "grailed", as_of="2026-06-15")
    versions = payload.data["versions"]
    assert len(versions) == 1
    assert versions[0]["fee_pct"] == pytest.approx(0.12)
    assert versions[0]["handle"] == "_snkr.haus"


def test_as_of_before_first_version_is_uncovered(warehouse):
    _build(warehouse)
    payload = get_channel_as_of(warehouse, "grailed", as_of="2024-12-31T23:59:59")
    assert payload.data["versions"] == []
    assert payload.data["covered"] is False


def test_unknown_platform(warehouse):
    _build(warehouse)
    with pytest.raises(KeyError, match="unknown channel"):
        get_channel_as_of(warehouse, "stockx")


def test_empty_platform(warehouse):
    with pytest.raises(ValueError, match="platform is required"):
        get_channel_as_of(warehouse, "  ")


def test_item_listing_platform_survives_later_channel_version(warehouse, tmp_path):
    """Listings stamp a version-specific channel_key. Closing that version
    must not drop platform on current-state item reads."""
    data = tmp_path / "src"
    data.mkdir()
    v1 = {
        "platform": "grailed",
        "handle": "h",
        "standing": "active",
        "region": "US",
        "fee_pct": 0.09,
        "valid_from": "2025-01-01T00:00:00",
    }
    v2 = {**v1, "fee_pct": 0.12, "valid_from": "2026-01-01T00:00:00"}
    item = {
        "sku": "x-1",
        "product": "X",
        "status": "listed",
        "acquisition_cost_cny": 100,
        "qty": 1,
        "target_price_usd": 50,
    }
    listing = {
        "item_sku": "x-1",
        "platform": "grailed",
        "platform_url": "https://grailed.com/x",
        "price_usd": 50.0,
        "status": "active",
        "listed_at": "2025-06-01T00:00:00",
    }

    (data / "channels.jsonl").write_text(json.dumps(v1) + "\n")
    assert ChannelIngest(warehouse, data).run()["status"] == "success"

    (data / "catalog_items.jsonl").write_text(json.dumps(item) + "\n")
    assert ItemIngest(warehouse, data).run()["status"] == "success"

    (data / "listings.jsonl").write_text(json.dumps(listing) + "\n")
    assert ListingIngest(warehouse, data).run()["status"] == "success"

    before = get_item(warehouse, "x-1")
    assert before.data["listings"][0]["platform"] == "grailed"

    (data / "channels.jsonl").write_text(json.dumps(v1) + "\n" + json.dumps(v2) + "\n")
    assert ChannelIngest(warehouse, data).run(force=True)["status"] == "success"

    after = get_item(warehouse, "x-1")
    assert after.data["listings"][0]["platform"] == "grailed"

    closed = warehouse.execute(
        """
        SELECT fee_pct, valid_to FROM core.channels
        WHERE platform='grailed' AND valid_to IS NOT NULL
        """
    ).fetchone()
    assert closed[0] == pytest.approx(0.09)
    assert str(closed[1]).startswith("2026-01-01")
