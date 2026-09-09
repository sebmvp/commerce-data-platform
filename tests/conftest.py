"""Shared fixtures: temporary PostgreSQL schema + sample data."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cdp_cli import db  # noqa: E402


@pytest.fixture()
def warehouse(monkeypatch):
    """Fresh schema in the test database for each test."""
    url = os.environ.get("CDP_TEST_DATABASE_URL", db.TEST_URL)
    monkeypatch.setenv("CDP_DATABASE_URL", url)
    monkeypatch.setenv("CDP_DATA", str(Path(__file__).resolve().parents[1] / "sample_data"))
    db.ensure_database(url)
    con = db.connect()
    db.reset_schema(con)
    yield con
    con.close()
