"""Shared ingest scaffolding: run audit, file hashing, quarantine, upserts.

Each source loader inherits `IngestJob`. Contract:

* validate every row with its pydantic model
* quarantine rejects into core.rejected_records (with reasons)
* upsert valid rows on the table's natural key — so re-runs are no-ops
* skip the whole file when its content hash matches the last success
  (idempotency at the batch level, not just the row level)
* always record a core.ingest_runs audit row
* each run is a single transaction: a mid-run exception rolls back every
  upsert from that run and still leaves a durable `failed` audit row
* orphaned `running` rows (process killed mid-run) are recovered to `failed`
  before the next write session starts
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Generic, TypeVar

from psycopg import Error as DatabaseError
from pydantic import BaseModel, ValidationError

from ..db import Connection

R = TypeVar("R", bound=BaseModel)

_ORPHAN_MSG = "orphaned: process interrupted before run completed"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def recover_orphaned_runs(con: Connection) -> int:
    """Mark any leftover `running` ingest audits as `failed`.

    A process kill mid-run can leave status='running' with no finished_at.
    Those rows make warehouse trustworthiness unreadable; recover them before
    the next write path starts. Returns the number of rows recovered.
    """
    before = con.execute(
        "SELECT count(*) FROM core.ingest_runs WHERE status = 'running'"
    ).fetchone()[0]
    if before == 0:
        return 0
    con.execute(
        """
        UPDATE core.ingest_runs
        SET status = 'failed',
            finished_at = COALESCE(finished_at, ?),
            error_message = COALESCE(error_message, ?)
        WHERE status = 'running'
        """,
        [_now(), _ORPHAN_MSG],
    )
    return int(before)


class IngestJob(Generic[R]):
    """One JSONL file -> one destination table."""

    source: str = ""
    filename: str = ""
    model: type[R]

    def __init__(self, con: Connection, data_dir: Path):
        self.con = con
        self.data_dir = data_dir
        self.path = data_dir / self.filename

    def upsert(self, rec: R, raw: dict[str, Any]) -> None:
        raise NotImplementedError

    def natural_key(self, rec: R) -> str:
        raise NotImplementedError

    def run(self, force: bool = False) -> dict[str, Any]:
        file_hash = file_sha256(self.path) if self.path.exists() else ""
        idem_key = hashlib.sha256(f"{self.source}:{file_hash}".encode()).hexdigest()[:16]

        if not force and self._already_succeeded(idem_key):
            return {"source": self.source, "skipped": True, "reason": "unchanged"}

        run_id = str(uuid.uuid4())
        started = _now()
        t0 = time.perf_counter()
        stats = {"read": 0, "loaded": 0, "rejected": 0}
        error: str | None = None
        status = "failed"

        self.con.execute("BEGIN")
        try:
            self.con.execute(
                """INSERT INTO core.ingest_runs
                   (run_id, source, file_path, file_hash, started_at, status, run_idempotency_key)
                   VALUES (?, ?, ?, ?, ?, 'running', ?)""",
                [run_id, self.source, str(self.path), file_hash, started, idem_key],
            )

            if not self.path.exists():
                raise FileNotFoundError(str(self.path))

            for line_no, line in enumerate(self.path.read_text().splitlines(), 1):
                line = line.strip()
                if not line:
                    continue
                stats["read"] += 1
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as je:
                    self._quarantine(
                        run_id,
                        {"_unparseable": line},
                        "malformed_json",
                        f"line {line_no}: {je.msg}",
                    )
                    stats["rejected"] += 1
                    continue
                try:
                    rec = self.model.model_validate(raw)
                except ValidationError as ve:
                    self._quarantine(
                        run_id,
                        raw,
                        "schema_violation",
                        "; ".join(
                            f"{'.'.join(map(str, e['loc']))}: {e['msg']}"
                            for e in ve.errors()
                        ),
                    )
                    stats["rejected"] += 1
                    continue
                try:
                    self.upsert(rec, raw)
                    stats["loaded"] += 1
                except (DatabaseError, ValueError) as e:
                    self._quarantine(run_id, raw, "load_error", str(e))
                    stats["rejected"] += 1

            status = "success"
            self.con.execute(
                """UPDATE core.ingest_runs
                   SET finished_at=?, status=?, rows_read=?, rows_loaded=?,
                       rows_rejected=?, error_message=?, duration_ms=?
                   WHERE run_id=?""",
                [
                    _now(),
                    status,
                    stats["read"],
                    stats["loaded"],
                    stats["rejected"],
                    None,
                    int((time.perf_counter() - t0) * 1000),
                    run_id,
                ],
            )
            self.con.execute("COMMIT")
        except Exception as e:
            error = str(e)
            status = "failed"
            try:
                self.con.execute("ROLLBACK")
            except DatabaseError:
                pass
            duration_ms = int((time.perf_counter() - t0) * 1000)
            stats["loaded"] = 0
            stats["rejected"] = 0
            self._record_failed_run(
                run_id=run_id,
                file_hash=file_hash,
                started=started,
                idem_key=idem_key,
                stats=stats,
                error=error,
                duration_ms=duration_ms,
            )

        return {
            "source": self.source,
            "status": status,
            **stats,
            "run_id": run_id,
            "error": error,
        }

    def _record_failed_run(
        self,
        *,
        run_id: str,
        file_hash: str,
        started: datetime,
        idem_key: str,
        stats: dict[str, int],
        error: str | None,
        duration_ms: int,
    ) -> None:
        self.con.execute("BEGIN")
        try:
            self.con.execute(
                """INSERT INTO core.ingest_runs
                   (run_id, source, file_path, file_hash, started_at, finished_at,
                    status, rows_read, rows_loaded, rows_rejected, error_message,
                    duration_ms, run_idempotency_key)
                   VALUES (?, ?, ?, ?, ?, ?, 'failed', ?, ?, ?, ?, ?, ?)""",
                [
                    run_id,
                    self.source,
                    str(self.path),
                    file_hash,
                    started,
                    _now(),
                    stats["read"],
                    stats["loaded"],
                    stats["rejected"],
                    error,
                    duration_ms,
                    idem_key,
                ],
            )
            self.con.execute("COMMIT")
        except Exception:
            try:
                self.con.execute("ROLLBACK")
            except DatabaseError:
                pass
            raise

    def _already_succeeded(self, idem_key: str) -> bool:
        row = self.con.execute(
            """SELECT 1 FROM core.ingest_runs
               WHERE run_idempotency_key = ? AND status = 'success' LIMIT 1""",
            [idem_key],
        ).fetchone()
        return row is not None

    def _quarantine(self, run_id: str, raw: dict[str, Any], code: str, detail: str) -> None:
        key = None
        for candidate in ("sku", "order_id", "content_id", "item_sku", "note_id"):
            if candidate in raw:
                key = f"{candidate}:{raw[candidate]}"
                break
        self.con.execute(
            """INSERT INTO core.rejected_records
               (rejected_id, run_id, source, record_key, error_code, detail, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?::jsonb)""",
            [
                str(uuid.uuid4()),
                run_id,
                self.source,
                key,
                code,
                detail,
                json.dumps(raw, default=str),
            ],
        )

    def _id(self, *parts: Any) -> str:
        return hashlib.sha256(":".join(str(p) for p in parts).encode()).hexdigest()[:16]


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            yield json.loads(line)
