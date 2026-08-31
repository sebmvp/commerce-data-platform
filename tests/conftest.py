"""Shared fixtures: temporary warehouse + temp sample data."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cdp_cli import db  # noqa: E402


@pytest.fixture()
def warehouse(tmp_path, monkeypatch):
    """Fresh warehouse + real sample_data for each test."""
    monkeypatch.setenv("CDP_DB", str(tmp_path / "test_warehouse.duckdb"))
    monkeypatch.setenv("CDP_DATA", str(Path(__file__).resolve().parents[1] / "sample_data"))
    con = db.connect()
    db.init_schema(con)
    yield con
    con.close()
    os.environ.pop("CDP_DB", None)
    os.environ.pop("CDP_DATA", None)
