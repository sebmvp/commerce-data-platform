"""Validation: pydantic models accept valid rows, reject broken ones."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from cdp_cli.validate import (
    ChannelRecord,
    ContentRecord,
    EngagementRecord,
    ItemRecord,
    ListingRecord,
)


def test_item_valid():
    rec = ItemRecord(sku="sku-1", product="Test", status="owned")
    assert rec.qty == 1


def test_item_rejects_negative_cost():
    with pytest.raises(ValidationError):
        ItemRecord(sku="x", product="y", acquisition_cost_cny=-50)


def test_item_rejects_bad_status():
    with pytest.raises(ValidationError):
        ItemRecord(sku="x", product="y", status="lost_in_mail")


def test_listing_requires_price():
    with pytest.raises(ValidationError):
        ListingRecord(item_sku="s", platform="grailed", price_usd=0,
                      listed_at="2026-05-01T00:00:00")


def test_listing_sold_requires_sold_price():
    with pytest.raises(ValidationError, match="sold_price"):
        ListingRecord(item_sku="s", platform="grailed", price_usd=100,
                      status="sold", listed_at="2026-05-01T00:00:00",
                      sold_at="2026-05-10T00:00:00")


def test_channel_valid():
    rec = ChannelRecord(platform="grailed", handle="h", valid_from="2025-01-01T00:00:00")
    assert rec.standing == "active"


def test_content_valid():
    rec = ContentRecord(content_id="p1", body="here", tone="minimal", status="published",
                        published_at="2026-05-01T00:00:00")
    assert rec.tone == "minimal"


def test_engagement_non_negative():
    with pytest.raises(ValidationError):
        EngagementRecord(listing_ref="x", platform="grailed",
                         snapshot_at="2026-06-01", views=-5)
