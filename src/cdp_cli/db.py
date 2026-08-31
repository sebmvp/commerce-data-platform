"""DuckDB connection management and warehouse bootstrap.

The warehouse file is a *cache*. Canonical truth lives in the JSONL source
files under the data directory; `init_schema` + ingest rebuilds everything.
"""
from __future__ import annotations

import os
from pathlib import Path

import duckdb

DEFAULT_DB_NAME = "warehouse.duckdb"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def db_path() -> Path:
    """Warehouse path, overridable via CDP_DB for tests / CI."""
    env = os.environ.get("CDP_DB")
    if env:
        return Path(env)
    return project_root() / DEFAULT_DB_NAME


def data_dir() -> Path:
    env = os.environ.get("CDP_DATA")
    if env:
        return Path(env)
    return project_root() / "sample_data"


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)


def init_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create schemas/tables (idempotent) and rebuild analytics views."""
    root = project_root()
    con.execute((root / "schema" / "001_init.sql").read_text())
    con.execute((root / "sql" / "views.sql").read_text())


def table_counts(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str, int]]:
    rows = con.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema IN ('core','catalog','supply','sales','insights')
          AND table_type = 'BASE TABLE'
        ORDER BY 1, 2
        """
    ).fetchall()
    out: list[tuple[str, str, int]] = []
    for schema, table in rows:
        n = con.execute(f'SELECT count(*) FROM "{schema}"."{table}"').fetchone()[0]
        out.append((schema, table, n))
    return out
