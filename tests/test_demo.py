"""End-to-end demo: readable story, no mutation of sample_data."""
from __future__ import annotations

import hashlib
from io import StringIO
from pathlib import Path

from cdp_cli.demo import run_demo

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
    assert "WAREHOUSE TRUST" in text
    assert "QUARANTINE" in text
    assert "malformed_json" in text
    assert "schema_violation" in text
    assert "valid items still 12" in text
    assert SAMPLE.read_text().count("{this is not json}") == 0
    assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest() == before
