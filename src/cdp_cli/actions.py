"""Sandbox operational actions.

Recommendations suggest. An Action is an intentional change that a human
approves or rejects. Nothing here writes marketplace APIs or the DuckDB
warehouse — the record *is* the operational state for now.

SQLite on purpose: one local operator, stdlib, no Docker. Postgres is the
next store if concurrent writers show up. Do not copy warehouse tables here.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .db import project_root

ACTION_TYPES = frozenset({
    "propose_list",
    "propose_reprice",
    "propose_channel_change",
    "mark_reviewed",
})
TARGET_TYPES = frozenset({"item", "listing"})
STATUSES = frozenset({"proposed", "approved", "rejected"})

# Heuristic recommendation action → sandbox action_type.
SANDBOX_FOR_REC = {
    "list_next": "propose_list",
    "review_price_or_channel": "propose_reprice",
    "consider_reprice": "propose_reprice",
    "monitor": "mark_reviewed",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (
  action_id TEXT PRIMARY KEY,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  proposed_payload TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  decided_at TEXT,
  actor TEXT NOT NULL,
  decided_by TEXT,
  recommendation_action TEXT,
  reason TEXT,
  decision_reason TEXT
)
"""


def actions_db_path() -> Path:
    env = os.environ.get("CDP_ACTIONS_DB")
    if env:
        return Path(env)
    return project_root() / "actions.sqlite"


def connect(path: Path | None = None) -> sqlite3.Connection:
    p = path or actions_db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p))
    con.row_factory = sqlite3.Row
    con.execute(_SCHEMA)
    return con


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"


def _row(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    raw = d.get("proposed_payload")
    if isinstance(raw, str):
        try:
            d["proposed_payload"] = json.loads(raw)
        except json.JSONDecodeError:
            pass
    return d


def _payload(kind: str, data: Any) -> dict[str, Any]:
    return {
        "kind": "action",
        "data": data,
        "provenance": {
            "tool": kind,
            "as_of": _now(),
            "source_relations": ["actions.sqlite"],
            "notes": [
                "ACTION is proposed/approved operational intent, not a warehouse fact.",
                "Does not mutate DuckDB or any marketplace. Sandbox only.",
            ],
        },
    }


def propose(
    *,
    target_type: str,
    target_id: str,
    action_type: str,
    reason: str,
    actor: str = "operator",
    payload: dict[str, Any] | None = None,
    recommendation_action: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    target_type = (target_type or "").strip()
    target_id = (target_id or "").strip()
    action_type = (action_type or "").strip()
    actor = (actor or "").strip() or "operator"
    reason = (reason or "").strip()
    if target_type not in TARGET_TYPES:
        raise ValueError(f"target_type must be one of {sorted(TARGET_TYPES)}")
    if not target_id:
        raise ValueError("target_id is required")
    if action_type not in ACTION_TYPES:
        raise ValueError(f"action_type must be one of {sorted(ACTION_TYPES)}")
    if not reason:
        raise ValueError("reason is required")

    rec = {
        "action_id": str(uuid.uuid4()),
        "target_type": target_type,
        "target_id": target_id,
        "action_type": action_type,
        "proposed_payload": payload or {},
        "status": "proposed",
        "created_at": _now(),
        "decided_at": None,
        "actor": actor,
        "decided_by": None,
        "recommendation_action": recommendation_action,
        "reason": reason,
        "decision_reason": None,
    }
    con = connect(path)
    try:
        con.execute(
            """
            INSERT INTO actions (
              action_id, target_type, target_id, action_type, proposed_payload,
              status, created_at, decided_at, actor, decided_by,
              recommendation_action, reason, decision_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                rec["action_id"], rec["target_type"], rec["target_id"],
                rec["action_type"], json.dumps(rec["proposed_payload"]),
                rec["status"], rec["created_at"], rec["decided_at"],
                rec["actor"], rec["decided_by"], rec["recommendation_action"],
                rec["reason"], rec["decision_reason"],
            ],
        )
        con.commit()
    finally:
        con.close()
    return _payload("propose_action", rec)


def get_action(action_id: str, *, path: Path | None = None) -> dict[str, Any]:
    action_id = (action_id or "").strip()
    if not action_id:
        raise ValueError("action_id is required")
    con = connect(path)
    try:
        row = con.execute(
            "SELECT * FROM actions WHERE action_id = ?", [action_id]
        ).fetchone()
    finally:
        con.close()
    if row is None:
        raise KeyError(f"unknown action_id={action_id!r}")
    return _payload("get_action", _row(row))


def list_actions(
    *,
    status: str | None = None,
    limit: int = 50,
    path: Path | None = None,
) -> dict[str, Any]:
    limit = max(1, min(int(limit), 200))
    sql = "SELECT * FROM actions"
    params: list[Any] = []
    if status:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {sorted(STATUSES)}")
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    con = connect(path)
    try:
        rows = [_row(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()
    return _payload("list_actions", {"actions": rows, "count": len(rows)})


def _decide(
    action_id: str,
    *,
    new_status: str,
    actor: str,
    decision_reason: str | None,
    path: Path | None,
) -> dict[str, Any]:
    action_id = (action_id or "").strip()
    actor = (actor or "").strip() or "operator"
    if not action_id:
        raise ValueError("action_id is required")
    con = connect(path)
    try:
        row = con.execute(
            "SELECT * FROM actions WHERE action_id = ?", [action_id]
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown action_id={action_id!r}")
        current = _row(row)
        if current["status"] != "proposed":
            raise ValueError(
                f"action {action_id} is {current['status']}, not proposed"
            )
        now = _now()
        con.execute(
            """
            UPDATE actions
            SET status = ?, decided_at = ?, decided_by = ?, decision_reason = ?
            WHERE action_id = ?
            """,
            [new_status, now, actor, decision_reason, action_id],
        )
        con.commit()
        row = con.execute(
            "SELECT * FROM actions WHERE action_id = ?", [action_id]
        ).fetchone()
        assert row is not None
        data = _row(row)
    finally:
        con.close()
    tool = "approve_action" if new_status == "approved" else "reject_action"
    return _payload(tool, data)


def approve_action(
    action_id: str,
    *,
    actor: str = "operator",
    reason: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    return _decide(
        action_id, new_status="approved", actor=actor,
        decision_reason=reason, path=path,
    )


def reject_action(
    action_id: str,
    *,
    actor: str = "operator",
    reason: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    return _decide(
        action_id, new_status="rejected", actor=actor,
        decision_reason=reason, path=path,
    )


def sandbox_type_for_recommendation(rec_action: str) -> str:
    try:
        return SANDBOX_FOR_REC[rec_action]
    except KeyError as e:
        raise ValueError(f"unknown recommendation action {rec_action!r}") from e
