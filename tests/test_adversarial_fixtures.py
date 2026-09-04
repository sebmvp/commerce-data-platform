"""Adversarial fixture suite: hostile inputs must not corrupt warehouse truth.

Committed fixtures under tests/fixtures/adversarial/ exercise:
  - duplicate natural keys in one file
  - schema violations (negative cost, null required fields, empty keys)
  - malformed JSON lines mid-file
  - referential misses (events for unknown items)
  - unknown enum values

Invariants: run stays success when only row-level failures occur; valid rows
load; rejects quarantine with codes; re-run is idempotent; trust stays OK
(all-reject is a warning, unbalanced would not be).
"""
from __future__ import annotations

import shutil
from pathlib import Path

from cdp_cli.ingest.catalog import ItemEventIngest, ItemIngest
from cdp_cli.observability import trust_report

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "adversarial"


def _stage(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    for name in ("catalog_items.jsonl", "item_events.jsonl"):
        shutil.copy(FIXTURES / name, data / name)
    return data


def test_adversarial_items_quarantine_and_keep_valid_rows(warehouse, tmp_path):
    data = _stage(tmp_path)
    result = ItemIngest(warehouse, data).run()

    assert result["status"] == "success"
    assert result["read"] >= 5
    assert result["loaded"] >= 3  # adv-ok-1,2,3 (dup upserts same sku)
    assert result["rejected"] >= 3

    skus = {
        r[0]
        for r in warehouse.execute("SELECT sku FROM catalog.items").fetchall()
    }
    assert "adv-ok-1" in skus
    assert "adv-ok-2" in skus
    assert "adv-ok-3" in skus
    assert "adv-neg" not in skus

    codes = {
        r[0]
        for r in warehouse.execute(
            "SELECT DISTINCT error_code FROM core.rejected_records WHERE source='catalog.items'"
        ).fetchall()
    }
    assert "malformed_json" in codes
    assert "schema_violation" in codes

    # Idempotent re-run
    second = ItemIngest(warehouse, data).run()
    assert second.get("skipped") is True
    (n_items,) = warehouse.execute("SELECT count(*) FROM catalog.items").fetchone()
    assert n_items == len(skus)


def test_adversarial_events_referential_and_schema(warehouse, tmp_path):
    data = _stage(tmp_path)
    # items first so referential check can pass for known skus
    ItemIngest(warehouse, data).run()
    result = ItemEventIngest(warehouse, data).run()

    assert result["status"] == "success"
    assert result["rejected"] >= 2  # unknown sku + bad enum + malformed
    assert result["loaded"] >= 2  # received+ordered for known items

    codes = {
        r[0]
        for r in warehouse.execute(
            "SELECT DISTINCT error_code FROM core.rejected_records "
            "WHERE source='catalog.item_events'"
        ).fetchall()
    }
    assert "load_error" in codes or "schema_violation" in codes
    assert "malformed_json" in codes


def test_adversarial_suite_keeps_trust_ok(warehouse, tmp_path):
    data = _stage(tmp_path)
    ItemIngest(warehouse, data).run()
    ItemEventIngest(warehouse, data).run()
    report = trust_report(warehouse)
    assert report.ok is True
    assert report.unbalanced_success_runs == 0
    # We expect some rejects, but they must be reconciled.
    assert report.total_rejected_records > 0
