"""Shared ingest run: identity, atomicity, quarantine, lineage.

JSONL jobs and source adapters both land here after adaptation.
Domain code decides how a source row becomes an Item or Listing.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from psycopg import Error as DatabaseError

from ..db import Connection
from .contract import AdaptedBatch, AdaptedRecord

ENTITY_ORDER = (
    "channel",
    "item",
    "item_event",
    "listing",
    "listing_event",
    "engagement",
    "order",
    "note",
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def write_lineage(con: Connection, rec: AdaptedRecord, *, ingest_run_id: str) -> None:
    lineage = rec.lineage
    lineage_id = hashlib.sha256(
        f"{rec.entity_type}:{rec.natural_key}:{ingest_run_id}:{lineage.content_hash}".encode()
    ).hexdigest()[:16]
    con.execute(
        """
        INSERT INTO core.record_lineage
          (lineage_id, entity_type, entity_id, source_system, source_record_reference,
           content_hash, observed_at, effective_at, ingest_run_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (lineage_id) DO NOTHING
        """,
        [
            lineage_id,
            rec.entity_type,
            rec.natural_key,
            lineage.source_system,
            lineage.source_record_reference,
            lineage.content_hash,
            lineage.observed_at,
            lineage.effective_at,
            ingest_run_id,
        ],
    )


def persist_adapted_batch(
    con: Connection,
    batch: AdaptedBatch,
    *,
    upsert: Callable[[AdaptedRecord], None],
    source: str,
    force: bool = True,
    file_path: str = "",
    file_hash: str = "",
) -> dict[str, Any]:
    """Write an adapted batch through one ingest run.

    `upsert` is domain-owned. This function owns the run row, transaction,
    quarantine, and lineage. Unknown effective timestamps stay NULL.
    """
    digest = file_hash or hashlib.sha256(
        json.dumps(
            [r.natural_key for r in batch.accepted],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    idem_key = hashlib.sha256(f"{source}:{digest}".encode()).hexdigest()[:16]
    if not force:
        row = con.execute(
            """SELECT 1 FROM core.ingest_runs
               WHERE run_idempotency_key = ? AND status = 'success' LIMIT 1""",
            [idem_key],
        ).fetchone()
        if row:
            return {"source": source, "skipped": True, "reason": "unchanged"}

    run_id = str(uuid.uuid4())
    started = _now()
    t0 = time.perf_counter()
    stats = {"read": 0, "loaded": 0, "rejected": 0}
    error: str | None = None
    status = "failed"

    con.execute("BEGIN")
    try:
        con.execute(
            """INSERT INTO core.ingest_runs
               (run_id, source, file_path, file_hash, started_at, status, run_idempotency_key)
               VALUES (?, ?, ?, ?, ?, 'running', ?)""",
            [run_id, source, file_path, digest, started, idem_key],
        )
        for rec in batch.rejects:
            stats["read"] += 1
            stats["rejected"] += 1
            _quarantine(con, run_id, source, rec)
        for rec in batch.accepted:
            stats["read"] += 1
            try:
                upsert(rec)
                write_lineage(con, rec, ingest_run_id=run_id)
                stats["loaded"] += 1
            except (DatabaseError, ValueError) as exc:
                rec.reject_reason = str(exc)
                _quarantine(con, run_id, source, rec)
                stats["rejected"] += 1
        status = "success"
        con.execute(
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
        con.execute("COMMIT")
    except Exception as exc:
        error = str(exc)
        status = "failed"
        try:
            con.execute("ROLLBACK")
        except DatabaseError:
            pass
        stats["loaded"] = 0
        con.execute("BEGIN")
        try:
            con.execute(
                """INSERT INTO core.ingest_runs
                   (run_id, source, file_path, file_hash, started_at, finished_at,
                    status, rows_read, rows_loaded, rows_rejected, error_message,
                    duration_ms, run_idempotency_key)
                   VALUES (?, ?, ?, ?, ?, ?, 'failed', ?, ?, ?, ?, ?, ?)""",
                [
                    run_id,
                    source,
                    file_path,
                    digest,
                    started,
                    _now(),
                    stats["read"],
                    0,
                    stats["rejected"],
                    error,
                    int((time.perf_counter() - t0) * 1000),
                    idem_key,
                ],
            )
            con.execute("COMMIT")
        except Exception:
            try:
                con.execute("ROLLBACK")
            except DatabaseError:
                pass
            raise

    return {
        "source": source,
        "status": status,
        **stats,
        "run_id": run_id,
        "error": error,
    }


def _quarantine(con: Connection, run_id: str, source: str, rec: AdaptedRecord) -> None:
    con.execute(
        """INSERT INTO core.rejected_records
           (rejected_id, run_id, source, record_key, error_code, detail, raw_json)
           VALUES (?, ?, ?, ?, ?, ?, ?::jsonb)""",
        [
            str(uuid.uuid4()),
            run_id,
            source,
            rec.natural_key,
            "adapter_reject" if rec.reject_reason else "load_error",
            rec.reject_reason or "rejected",
            json.dumps(rec.payload, default=str),
        ],
    )


def dummy_job_dir() -> Path:
    return Path("adapter://")
