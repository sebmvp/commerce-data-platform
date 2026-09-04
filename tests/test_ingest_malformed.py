"""Failure-path ingest: one malformed line must not abort the batch.

Regression guard for the case where a source file contains a corrupt
(non-JSON) line. The invariant: the run stays `success`, the bad line is
quarantined with error_code='malformed_json', and every valid row — including
rows *after* the corrupt line — is still loaded.
"""
from __future__ import annotations

import json

from cdp_cli.ingest.catalog import ItemIngest


def _write_items(path, rows):
    path.write_text("\n".join(rows) + "\n")


def test_malformed_json_line_is_quarantined_and_run_continues(warehouse, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    valid_before = {"sku": "sku-ok-1", "product": "Jordan 1", "status": "owned"}
    valid_after = {"sku": "sku-ok-2", "product": "Dunk Low", "status": "owned"}
    corrupt_line = '{"sku": "sku-broken", "product": '  # truncated JSON
    bad_schema = json.dumps({"sku": "sku-nocost", "product": "X",
                             "acquisition_cost_cny": -10})

    _write_items(
        data_dir / "catalog_items.jsonl",
        [json.dumps(valid_before), corrupt_line, bad_schema, json.dumps(valid_after)],
    )

    result = ItemIngest(warehouse, data_dir).run()

    # The run as a whole succeeds despite two bad rows.
    assert result["status"] == "success", result
    assert result["read"] == 4
    assert result["loaded"] == 2
    assert result["rejected"] == 2

    # Both valid rows — including the one AFTER the corrupt line — landed.
    skus = {r[0] for r in warehouse.execute("SELECT sku FROM catalog.items").fetchall()}
    assert skus == {"sku-ok-1", "sku-ok-2"}

    # Rejects are quarantined with distinguishable reasons, raw text preserved.
    rows = warehouse.execute(
        """SELECT error_code, record_key, raw_json
           FROM core.rejected_records ORDER BY created_at, rejected_id"""
    ).fetchall()
    codes = sorted(r[0] for r in rows)
    assert codes == ["malformed_json", "schema_violation"]

    malformed = next(r for r in rows if r[0] == "malformed_json")
    assert malformed[1] is None  # no natural key parseable from corrupt JSON
    assert "sku-broken" in malformed[2]  # raw line kept for debugging


def test_malformed_run_does_not_count_as_idempotent_success(warehouse, tmp_path):
    """A file containing only a corrupt line still records a successful run
    (quarantine is the failure handling), and re-running it is skipped."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_items(data_dir / "catalog_items.jsonl",
                 [json.dumps({"sku": "sku-ok", "product": "P", "status": "owned"}),
                  "{not json"])

    first = ItemIngest(warehouse, data_dir).run()
    assert first["status"] == "success" and first["rejected"] == 1
    second = ItemIngest(warehouse, data_dir).run()
    assert second.get("skipped"), "unchanged file should skip on re-run"
    (n_rejected,) = warehouse.execute(
        "SELECT count(*) FROM core.rejected_records").fetchone()
    assert n_rejected == 1, "re-run must not duplicate quarantine rows"
