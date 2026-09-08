"""End-to-end demo: readable story, no mutation of sample_data."""
from __future__ import annotations

import hashlib
import os
from io import StringIO
from pathlib import Path

from cdp_cli.demo import _isolated_warehouse, run_demo

SAMPLE = Path(__file__).resolve().parents[1] / "sample_data" / "catalog_items.jsonl"


def test_demo_story_and_sample_untouched(tmp_path, monkeypatch):
    before = hashlib.sha256(SAMPLE.read_bytes()).hexdigest()
    monkeypatch.setenv("CDP_DB", str(tmp_path / "demo.duckdb"))
    monkeypatch.setenv("CDP_DATA", str(SAMPLE.parent))

    buf = StringIO()
    rc = run_demo(file=buf)
    text = buf.getvalue()

    assert rc == 0
    assert "BUSINESS STATE" in text
    assert "ATTENTION" in text
    assert "LIST NEXT" in text
    assert "ITEM HISTORY" in text
    assert "stone-cargo-l" in text
    assert "SANDBOX ACTION" in text
    assert "human approved" in text
    assert "WAREHOUSE TRUST" in text
    assert "QUARANTINE" in text
    assert "malformed_json" in text
    assert "schema_violation" in text
    assert "valid items still 12" in text
    assert SAMPLE.read_text().count("{this is not json}") == 0
    assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest() == before


def test_demo_does_not_delete_configured_warehouse(tmp_path, monkeypatch):
    """cdp demo must never unlink CDP_DB / an operator's warehouse."""
    configured = tmp_path / "operator.duckdb"
    sentinel = b"SENTINEL-NOT-A-WAREHOUSE"
    configured.write_bytes(sentinel)
    monkeypatch.setenv("CDP_DB", str(configured))
    monkeypatch.setenv("CDP_DATA", str(SAMPLE.parent))

    buf = StringIO()
    rc = run_demo(file=buf)
    text = buf.getvalue()

    assert rc == 0
    assert configured.exists()
    assert configured.read_bytes() == sentinel
    assert os.environ.get("CDP_DB") == str(configured)
    assert "isolated warehouse" in text
    assert str(configured) not in text


def test_isolated_warehouse_restores_configured_env(tmp_path, monkeypatch):
    configured = str(tmp_path / "keep.duckdb")
    monkeypatch.setenv("CDP_DB", configured)
    with _isolated_warehouse() as path:
        assert os.environ["CDP_DB"] == str(path)
        assert path != Path(configured)
    assert os.environ["CDP_DB"] == configured


def test_isolated_warehouse_restores_unset_env(monkeypatch):
    monkeypatch.delenv("CDP_DB", raising=False)
    with _isolated_warehouse():
        assert "CDP_DB" in os.environ
    assert "CDP_DB" not in os.environ
