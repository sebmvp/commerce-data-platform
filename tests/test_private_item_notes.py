"""Sanitized item-note adapter tests. Fixtures are fictional."""
from __future__ import annotations

from pathlib import Path

from cdp_cli.domains.resale.adapters.item_notes import (
    note_to_records,
    parse_item_note,
    slug_sku,
)
from cdp_cli.domains.resale.adapters.private import (
    ingest_private,
    materialize_item_notes,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "item_notes"


def test_slug_sku_matches_item_scoped_pattern() -> None:
    assert slug_sku("Canvas Tote — Black OS") == "canvas-tote-black-os"


def test_listed_note_emits_item_listing_and_lineage() -> None:
    parsed = parse_item_note(FIXTURES / "Canvas Tote — Black OS.md")
    result = note_to_records(parsed)
    assert result["reject"] is None
    item = result["records"]["item"]
    assert item["sku"] == "canvas-tote-black-os"
    assert item["acquisition_cost_cny"] == 38.5
    assert item["_lineage"]["source_system"] == "obsidian_item_notes"
    assert item["_lineage"]["source_record_reference"] == "Canvas Tote — Black OS.md"
    assert result["records"]["listings"][0]["platform"] == "grailed"
    assert "grailed.example" in result["records"]["listings"][0]["platform_url"]


def test_owned_unlisted_has_no_listing() -> None:
    parsed = parse_item_note(FIXTURES / "Work Shirt — Olive M.md")
    result = note_to_records(parsed)
    assert result["records"]["item"]["status"] == "owned"
    assert result["records"]["listings"] == []


def test_broken_note_is_rejected() -> None:
    parsed = parse_item_note(FIXTURES / "Broken Note.md")
    result = note_to_records(parsed)
    assert result["reject"]
    assert result["records"] is None


def test_materialize_writes_staging_without_personal_paths(tmp_path: Path) -> None:
    summary = materialize_item_notes(FIXTURES, tmp_path)
    assert summary["items"] == 3
    assert summary["rejected"] >= 1
    catalog = (tmp_path / "catalog_items.jsonl").read_text()
    assert "offamacbook" not in catalog
    assert "Documents" not in catalog
    assert "source_system" in catalog


def test_ingest_private_into_isolated_database(tmp_path, monkeypatch) -> None:
    url = "postgresql://cdp:cdp@127.0.0.1:5432/cdp_private_test"
    monkeypatch.setenv("CDP_PRIVATE_SOURCE", str(FIXTURES))
    monkeypatch.setenv("CDP_PRIVATE_STAGING", str(tmp_path / "staging"))
    monkeypatch.setenv("CDP_PRIVATE_DATABASE_URL", url)
    from cdp_cli import db

    db.ensure_database(url)
    summary = ingest_private(source=FIXTURES, database_url=url, force=True)
    assert summary["items"] == 3
    con = db.connect(url=url)
    try:
        n = con.execute("SELECT count(*) FROM catalog.items").fetchone()[0]
        assert n == 3
        row = con.execute(
            "SELECT sku, raw_json->>'source_system' FROM catalog.items WHERE sku=?",
            ["canvas-tote-black-os"],
        ).fetchone()
        assert row[1] == "obsidian_item_notes"
    finally:
        con.close()
