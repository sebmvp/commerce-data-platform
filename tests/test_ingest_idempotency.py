"""Idempotency: re-running ingest on unchanged files is a no-op."""
from __future__ import annotations

from cdp_cli import db
from cdp_cli.ingest import ALL_JOBS


def test_second_run_skips_unchanged_files(warehouse):
    first = [j(warehouse, db.data_dir()).run() for j in ALL_JOBS]
    assert all(r.get("status") == "success" or r.get("skipped") for r in first)

    second = [j(warehouse, db.data_dir()).run() for j in ALL_JOBS]
    assert all(r.get("skipped") for r in second), (
        f"expected all skipped, got: {[r for r in second if not r.get('skipped')]}")

    # row counts unchanged after second run
    (n_items_first,) = warehouse.execute("SELECT count(*) FROM catalog.items").fetchone()
    assert n_items_first == 12
    (n_runs,) = warehouse.execute(
        "SELECT count(*) FROM core.ingest_runs WHERE status='success'").fetchone()
    assert n_runs == len(ALL_JOBS), "second run should not add new audit rows"

