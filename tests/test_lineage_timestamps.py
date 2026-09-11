"""Per-record lineage timestamps match the record's meaning."""
from __future__ import annotations

from pathlib import Path

from cdp_cli.domains.resale.adapters.item_notes import (
    ItemNotesAdapter,
    note_to_records,
    parse_item_note,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "item_notes"


def test_listing_effective_at_is_listed_at() -> None:
    batch = ItemNotesAdapter(FIXTURES).adapt()
    listing = next(
        r
        for r in batch.accepted
        if r.entity_type == "listing" and r.payload.get("item_sku") == "canvas-tote-black-os"
    )
    assert listing.lineage.effective_at is not None
    assert listing.lineage.effective_at.isoformat(timespec="seconds") == "2026-08-01T12:00:00"
    item = next(r for r in batch.accepted if r.natural_key == "canvas-tote-black-os")
    assert item.lineage.effective_at is None
    note = next(r for r in batch.accepted if r.entity_type == "note")
    assert note.lineage.effective_at is None


def test_inferred_received_has_null_event_at() -> None:
    parsed = parse_item_note(FIXTURES / "Work Shirt — Olive M.md")
    result = note_to_records(parsed)
    received = [e for e in result["records"]["events"] if e["event_type"] == "received"]
    assert received
    assert received[0]["event_at"] is None
    assert received[0]["payload"]["assertion"] == "inferred_from_status"
    assert received[0]["payload"]["verification"] == "unverified"


def test_disagreeing_prices_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "Split Price — OS.md"
    path.write_text(
        """---
type: reseller_item
product: Split Price
stream: Selling
status: owned
target_price_usd: 40
grailed_price_usd: 65
---
conflict
"""
    )
    parsed = parse_item_note(path)
    result = note_to_records(parsed)
    assert result["reject"]
    assert "disagree" in result["reject"]
