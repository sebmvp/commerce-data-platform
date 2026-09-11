"""Synthetic world invariants. Runtime platform does not import synthetic/."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from synthetic.resale.calibration import CALIBRATED, DIMENSIONS, ILLUSTRATIVE
from synthetic.resale.validate import validate_world


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _world(data_dir: Path) -> dict:
    return {
        "items": _jsonl(data_dir / "catalog_items.jsonl"),
        "listings": _jsonl(data_dir / "listings.jsonl"),
        "item_events": _jsonl(data_dir / "item_events.jsonl"),
        "listing_events": _jsonl(data_dir / "listing_events.jsonl"),
        "orders": _jsonl(data_dir / "orders.jsonl"),
        "engagement": _jsonl(data_dir / "engagement_metrics.jsonl"),
    }


def test_demo_world_satisfies_invariants() -> None:
    errors = validate_world(_world(ROOT / "sample_data"))
    assert errors == []


def test_heldout_world_satisfies_invariants() -> None:
    errors = validate_world(_world(ROOT / "sample_data_heldout"))
    assert errors == []


def test_demo_and_heldout_do_not_share_skus() -> None:
    demo = {row["sku"] for row in _jsonl(ROOT / "sample_data" / "catalog_items.jsonl")}
    held = {row["sku"] for row in _jsonl(ROOT / "sample_data_heldout" / "catalog_items.jsonl")}
    assert demo.isdisjoint(held)


def test_calibration_distinguishes_illustrative_from_calibrated() -> None:
    assert DIMENSIONS["operation_size"] == CALIBRATED
    assert DIMENSIONS["dual_channel"] == ILLUSTRATIVE
    assert "engagement_paths" in DIMENSIONS
