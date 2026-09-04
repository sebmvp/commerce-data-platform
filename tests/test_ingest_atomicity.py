"""Atomic run boundaries: a mid-run crash must not leave partial truth.

Invariants under test:
1. A file-level exception rolls back every upsert from that run, and records a
   `failed` audit row that survives the rollback.
2. Orphaned `running` audit rows (process killed mid-run) are recovered to
   `failed` before the next ingest starts.
3. Happy-path success still commits loaded rows + audit together.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cdp_cli import db
from cdp_cli.ingest.base import recover_orphaned_runs
from cdp_cli.ingest.catalog import ItemIngest
from cdp_cli.validate import ItemRecord


class _BoomOnSecondItem(ItemIngest):
    """Fails the batch after the first successful upsert — simulates mid-run crash."""

    def __init__(self, con, data_dir: Path):
        super().__init__(con, data_dir)
        self._seen = 0

    def upsert(self, rec: ItemRecord, raw: dict[str, Any]) -> None:
        self._seen += 1
        super().upsert(rec, raw)
        if self._seen >= 2:
            raise RuntimeError("simulated mid-run crash")


def _write_items(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def test_mid_run_exception_rolls_back_partial_load(warehouse, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_items(
        data_dir / "catalog_items.jsonl",
        [
            {"sku": "sku-a", "product": "A", "status": "owned", "acquisition_cost_cny": 100},
            {"sku": "sku-b", "product": "B", "status": "owned", "acquisition_cost_cny": 200},
            {"sku": "sku-c", "product": "C", "status": "owned", "acquisition_cost_cny": 300},
        ],
    )

    result = _BoomOnSecondItem(warehouse, data_dir).run()

    assert result["status"] == "failed"
    assert "simulated mid-run crash" in (result.get("error") or "")

    # No partial truth: neither the first upsert nor later ones survive.
    (n_items,) = warehouse.execute("SELECT count(*) FROM catalog.items").fetchone()
    assert n_items == 0

    runs = warehouse.execute(
        """SELECT status, rows_loaded, rows_rejected, error_message
           FROM core.ingest_runs WHERE source='catalog.items'"""
    ).fetchall()
    assert len(runs) == 1
    status, loaded, _rejected, err = runs[0]
    assert status == "failed"
    assert loaded == 0  # rolled back; audit reports post-rollback truth
    assert "simulated mid-run crash" in (err or "")


def test_orphan_running_rows_are_recovered_to_failed(warehouse):
    warehouse.execute(
        """INSERT INTO core.ingest_runs
           (run_id, source, file_path, file_hash, started_at, status, run_idempotency_key)
           VALUES ('orphan-1', 'catalog.items', 'x', 'h', current_timestamp,
                   'running', 'k1')"""
    )
    warehouse.execute(
        """INSERT INTO core.ingest_runs
           (run_id, source, file_path, file_hash, started_at, status, run_idempotency_key)
           VALUES ('ok-1', 'sales.orders', 'y', 'h2', current_timestamp,
                   'success', 'k2')"""
    )

    n = recover_orphaned_runs(warehouse)
    assert n == 1

    rows = {
        r[0]: r[1]
        for r in warehouse.execute(
            "SELECT run_id, status FROM core.ingest_runs"
        ).fetchall()
    }
    assert rows["orphan-1"] == "failed"
    assert rows["ok-1"] == "success"

    (msg,) = warehouse.execute(
        "SELECT error_message FROM core.ingest_runs WHERE run_id='orphan-1'"
    ).fetchone()
    assert msg and "orphan" in msg.lower()


def test_recover_runs_before_ingest_start(warehouse, tmp_path, monkeypatch):
    """cmd path: recovery is invoked so a stale 'running' never blocks trust."""
    warehouse.execute(
        """INSERT INTO core.ingest_runs
           (run_id, source, started_at, status)
           VALUES ('stale', 'core.channels', current_timestamp, 'running')"""
    )
    # recovery is part of init_schema / connect-for-write contract
    db.init_schema(warehouse)
    (status,) = warehouse.execute(
        "SELECT status FROM core.ingest_runs WHERE run_id='stale'"
    ).fetchone()
    assert status == "failed"


def test_successful_run_still_commits(warehouse, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_items(
        data_dir / "catalog_items.jsonl",
        [
            {"sku": "sku-ok", "product": "Ok", "status": "owned", "acquisition_cost_cny": 50},
        ],
    )
    result = ItemIngest(warehouse, data_dir).run()
    assert result["status"] == "success"
    assert result["loaded"] == 1
    (n,) = warehouse.execute("SELECT count(*) FROM catalog.items").fetchone()
    assert n == 1
    (status,) = warehouse.execute(
        "SELECT status FROM core.ingest_runs WHERE source='catalog.items'"
    ).fetchone()
    assert status == "success"
