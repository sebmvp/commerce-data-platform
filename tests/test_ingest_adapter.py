"""Source adapter contract is independent of JSONL files."""
from __future__ import annotations

from pathlib import Path

from cdp_cli.domains.resale.adapters.item_notes import ItemNotesAdapter
from cdp_cli.ingest.contract import AdaptedBatch

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "item_notes"


def test_item_notes_adapter_returns_lineage_without_writing() -> None:
    batch = ItemNotesAdapter(FIXTURES).adapt()
    assert isinstance(batch, AdaptedBatch)
    assert batch.source_system == "obsidian_item_notes"
    skus = {r.natural_key for r in batch.accepted if r.entity_type == "item"}
    assert "canvas-tote-black-os" in skus
    assert "work-shirt-olive-m" in skus
    item = next(r for r in batch.accepted if r.natural_key == "canvas-tote-black-os")
    assert item.lineage.source_record_reference.endswith(".md")
    assert item.lineage.content_hash
    assert item.payload.get("condition") is None
    owned = next(r for r in batch.accepted if r.natural_key == "work-shirt-olive-m")
    assert owned.payload["status"] == "owned"
    assert owned.payload.get("acquisition_channel") == "Example Supplier Co"
    listings = [
        r
        for r in batch.accepted
        if r.entity_type == "listing" and r.payload.get("item_sku") == "work-shirt-olive-m"
    ]
    assert listings == []
