"""End-to-end demo: readable story, no mutation of sample_data."""
from __future__ import annotations

import hashlib
import os
from io import StringIO
from pathlib import Path

from cdp_cli import db
from cdp_cli.demo import _isolated_warehouse, run_demo

SAMPLE = Path(__file__).resolve().parents[1] / "sample_data" / "catalog_items.jsonl"


def test_demo_story_and_sample_untouched(monkeypatch):
    before = hashlib.sha256(SAMPLE.read_bytes()).hexdigest()
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
    assert "valid items still" in text
    assert SAMPLE.read_text().count("{this is not json}") == 0
    assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest() == before


def test_demo_does_not_delete_configured_warehouse(warehouse, monkeypatch):
    warehouse.execute(
        """INSERT INTO core.ingest_runs
           (run_id, source, started_at, status)
           VALUES ('sentinel', 'operator', current_timestamp, 'success')"""
    )
    configured = db.database_url()
    monkeypatch.setenv("CDP_DATA", str(SAMPLE.parent))

    buf = StringIO()
    rc = run_demo(file=buf)
    text = buf.getvalue()

    assert rc == 0
    assert os.environ.get("CDP_DATABASE_URL") == configured
    (status,) = warehouse.execute(
        "SELECT status FROM core.ingest_runs WHERE run_id='sentinel'"
    ).fetchone()
    assert status == "success"
    assert "isolated warehouse" in text
    assert configured not in text


def test_isolated_warehouse_restores_configured_env(monkeypatch):
    configured = "postgresql://cdp:cdp@127.0.0.1:5432/cdp_keep"
    monkeypatch.setenv("CDP_DATABASE_URL", configured)
    with _isolated_warehouse() as url:
        assert os.environ["CDP_DATABASE_URL"] == url
        assert url != configured
    assert os.environ["CDP_DATABASE_URL"] == configured


def test_isolated_warehouse_restores_unset_env(monkeypatch):
    monkeypatch.delenv("CDP_DATABASE_URL", raising=False)
    with _isolated_warehouse():
        assert "CDP_DATABASE_URL" in os.environ
    assert "CDP_DATABASE_URL" not in os.environ
