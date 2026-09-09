"""PostgreSQL connection management and schema bootstrap.

PostgreSQL is the canonical operational store. Public synthetic JSONL under
sample_data/ is seed input, not a second source of truth.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse, urlunparse

import psycopg
from psycopg import Error as DatabaseError

DEFAULT_URL = "postgresql://cdp:cdp@127.0.0.1:5432/cdp"
TEST_URL = "postgresql://cdp:cdp@127.0.0.1:5432/cdp_test"
DEMO_URL = "postgresql://cdp:cdp@127.0.0.1:5432/cdp_demo"
SCHEMAS = ("core", "catalog", "supply", "sales", "insights", "ops")


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def database_url() -> str:
    env = os.environ.get("CDP_DATABASE_URL")
    if env:
        return env
    legacy = os.environ.get("CDP_DB")
    if legacy and legacy.startswith("postgres"):
        return legacy
    return DEFAULT_URL


def db_path() -> Path:
    """Deprecated alias kept for callers that printed a warehouse path."""
    return Path(database_url())


def data_dir() -> Path:
    env = os.environ.get("CDP_DATA")
    if env:
        return Path(env)
    return project_root() / "sample_data"


def _dbname(url: str) -> str:
    path = urlparse(url).path.lstrip("/")
    return path.split("?")[0] or "cdp"


def admin_url(url: str | None = None) -> str:
    parsed = urlparse(url or database_url())
    return urlunparse(parsed._replace(path="/postgres"))


def url_with_db(url: str, name: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path=f"/{name}"))


def _qmarks(sql: str) -> str:
    """Translate DuckDB-style ? placeholders to psycopg %s."""
    return sql.replace("%", "%%").replace("?", "%s")


_DOLLAR = re.compile(r"\$\$")


def iter_statements(script: str) -> list[str]:
    """Split SQL on semicolons, respecting 'strings' and $$ dollar quotes."""
    out: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(script)
    while i < n:
        if script.startswith("$$", i):
            j = script.find("$$", i + 2)
            if j < 0:
                buf.append(script[i:])
                break
            buf.append(script[i : j + 2])
            i = j + 2
            continue
        ch = script[i]
        if ch == "'":
            j = i + 1
            while j < n:
                if script[j] == "'":
                    if j + 1 < n and script[j + 1] == "'":
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            buf.append(script[i:j])
            i = j
            continue
        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                out.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    keep: list[str] = []
    for stmt in out:
        lines = [
            ln
            for ln in stmt.splitlines()
            if ln.strip() and not ln.strip().startswith("--")
        ]
        if lines:
            keep.append(stmt)
    return keep


class Result:
    def __init__(self, cur: psycopg.Cursor) -> None:
        self._cur = cur
        self.description = cur.description

    def fetchall(self) -> list[tuple]:
        if self._cur.description is None:
            return []
        return list(self._cur.fetchall())

    def fetchone(self) -> tuple | None:
        if self._cur.description is None:
            return None
        return self._cur.fetchone()


class Connection:
    """Small adapter so existing `con.execute(sql, params).fetchall()` keeps working."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn
        self._cur = conn.cursor()

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Result:
        converted = _qmarks(sql)
        if params is None:
            self._cur.execute(converted)
        else:
            self._cur.execute(converted, list(params))
        return Result(self._cur)

    def close(self) -> None:
        try:
            self._cur.close()
        finally:
            self._conn.close()

    def raw(self) -> psycopg.Connection:
        return self._conn


def connect(read_only: bool = False, url: str | None = None) -> Connection:
    conn = psycopg.connect(url or database_url(), autocommit=True)
    if read_only:
        with conn.cursor() as cur:
            cur.execute("SET default_transaction_read_only = on")
    return Connection(conn)


def connect_admin() -> psycopg.Connection:
    return psycopg.connect(admin_url(), autocommit=True)


def ensure_database(url: str | None = None) -> None:
    """Create the target database if the server is up and it is missing."""
    target = url or database_url()
    name = _dbname(target)
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name):
        raise ValueError(f"unsafe database name {name!r}")
    admin = connect_admin()
    try:
        row = admin.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", [name]
        ).fetchone()
        if row is None:
            admin.execute(f"CREATE DATABASE {name}")
    finally:
        admin.close()


def drop_database(url: str) -> None:
    name = _dbname(url)
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name):
        raise ValueError(f"unsafe database name {name!r}")
    admin = connect_admin()
    try:
        admin.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = %s AND pid <> pg_backend_pid()
            """,
            [name],
        )
        admin.execute(f"DROP DATABASE IF EXISTS {name}")
    finally:
        admin.close()


def exec_script(con: Connection, script: str) -> None:
    for stmt in iter_statements(script):
        con.execute(stmt)


def reset_schema(con: Connection) -> None:
    for schema in SCHEMAS:
        con.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    con.execute("DROP TABLE IF EXISTS alembic_version")
    init_schema(con)


def init_schema(con: Connection) -> None:
    """Create schemas/tables (idempotent) and rebuild analytics views."""
    root = project_root()
    exec_script(con, (root / "schema" / "001_init.sql").read_text())
    exec_script(con, (root / "sql" / "views.sql").read_text())
    from .ingest.base import recover_orphaned_runs

    recover_orphaned_runs(con)


def ping(url: str | None = None) -> bool:
    try:
        con = connect(url=url)
        try:
            con.execute("SELECT 1")
            return True
        finally:
            con.close()
    except Exception:
        return False


def table_counts(con: Connection) -> list[tuple[str, str, int]]:
    rows = con.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema IN ('core','catalog','supply','sales','insights','ops')
          AND table_type = 'BASE TABLE'
        ORDER BY 1, 2
        """
    ).fetchall()
    out: list[tuple[str, str, int]] = []
    for schema, table in rows:
        n = con.execute(f'SELECT count(*) FROM "{schema}"."{table}"').fetchone()[0]
        out.append((schema, table, n))
    return out


def is_initialized(con: Connection | None = None) -> bool:
    own = con is None
    if own:
        try:
            con = connect(read_only=True)
        except Exception:
            return False
    assert con is not None
    try:
        row = con.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'catalog' AND table_name = 'items'
            """
        ).fetchone()
        return row is not None
    except Exception:
        return False
    finally:
        if own:
            con.close()
