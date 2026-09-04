"""Reconciliation + trust signals for cdp status."""
from __future__ import annotations

import json
from pathlib import Path

from cdp_cli.ingest.catalog import ItemIngest
from cdp_cli.observability import latest_runs, trust_report


def _write_items(path: Path, rows: list[str]) -> None:
    path.write_text("\n".join(rows) + "\n")


def test_balanced_success_is_trustworthy(warehouse):
    from cdp_cli import db
    from cdp_cli.ingest import ALL_JOBS

    for j in ALL_JOBS:
        j(warehouse, db.data_dir()).run()

    report = trust_report(warehouse)
    assert report.ok
    assert report.orphaned_running == 0
    assert report.unbalanced_success_runs == 0
    assert report.total_rejected_records == 0
    assert any(r.status == "success" and r.balanced for r in report.recent_runs)


def test_all_reject_run_is_flagged_but_balanced(warehouse, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Valid JSON that fails schema (negative cost).
    _write_items(
        data_dir / "catalog_items.jsonl",
        [json.dumps({"sku": "x", "product": "P", "acquisition_cost_cny": -1})],
    )
    result = ItemIngest(warehouse, data_dir).run()
    assert result["status"] == "success"
    assert result["loaded"] == 0 and result["rejected"] == 1

    report = trust_report(warehouse)
    # Pipeline did its job — not a hard integrity failure.
    assert report.ok
    assert report.all_reject_success_runs == 1
    assert any("all rows rejected" in r for r in report.reasons)

    runs = latest_runs(warehouse)
    assert runs[0].all_rejected is True
    assert runs[0].balanced is True


def test_orphaned_running_fails_trust(warehouse):
    warehouse.execute(
        """INSERT INTO core.ingest_runs
           (run_id, source, started_at, status)
           VALUES ('live-orphan', 'catalog.items', current_timestamp, 'running')"""
    )
    report = trust_report(warehouse)
    assert report.ok is False
    assert report.orphaned_running == 1
    assert any("orphaned" in r for r in report.reasons)


def test_unbalanced_success_fails_trust(warehouse):
    warehouse.execute(
        """INSERT INTO core.ingest_runs
           (run_id, source, started_at, status, rows_read, rows_loaded, rows_rejected)
           VALUES ('drift', 'sales.orders', current_timestamp, 'success', 10, 3, 2)"""
    )
    report = trust_report(warehouse)
    assert report.ok is False
    assert report.unbalanced_success_runs == 1
    assert any("reconciliation" in r for r in report.reasons)
