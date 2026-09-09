"""Sandbox operational actions.

Recommendations suggest. An Action is an intentional change that a human
approves or rejects. Nothing here writes marketplace APIs or mutates
catalog/sales tables — the record *is* the operational state for now.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from . import db

ACTION_TYPES = frozenset({
    "propose_list",
    "propose_reprice",
    "propose_channel_change",
    "mark_reviewed",
})
TARGET_TYPES = frozenset({"item", "listing"})
STATUSES = frozenset({"proposed", "approved", "rejected"})

SANDBOX_FOR_REC = {
    "list_next": "propose_list",
    "review_price_or_channel": "propose_reprice",
    "consider_reprice": "propose_reprice",
    "monitor": "mark_reviewed",
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds") + "Z"


def _row(rec: dict[str, Any]) -> dict[str, Any]:
    payload = rec.get("proposed_payload")
    if isinstance(payload, str):
        try:
            rec["proposed_payload"] = json.loads(payload)
        except json.JSONDecodeError:
            pass
    for key in ("created_at", "decided_at"):
        val = rec.get(key)
        if hasattr(val, "isoformat"):
            rec[key] = val.isoformat(timespec="seconds") + "Z"
    return rec


def _payload(kind: str, data: Any) -> dict[str, Any]:
    return {
        "kind": "action",
        "data": data,
        "provenance": {
            "tool": kind,
            "as_of": _now_iso(),
            "source_relations": ["ops.actions"],
            "notes": [
                "ACTION is proposed/approved operational intent, not a catalog fact.",
                "Does not mutate listings/items or any marketplace. Sandbox only.",
            ],
        },
    }


def _fetch(con, action_id: str) -> dict[str, Any] | None:
    rel = con.execute("SELECT * FROM ops.actions WHERE action_id = ?", [action_id])
    cols = [c[0] for c in rel.description]
    row = rel.fetchone()
    if row is None:
        return None
    return _row(dict(zip(cols, row)))


def propose(
    *,
    target_type: str,
    target_id: str,
    action_type: str,
    reason: str,
    actor: str = "operator",
    payload: dict[str, Any] | None = None,
    recommendation_action: str | None = None,
    path: Any = None,
) -> dict[str, Any]:
    del path  # actions live in the canonical Postgres store
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
    con = db.connect()
    try:
        con.execute(
            """
            INSERT INTO ops.actions (
              action_id, target_type, target_id, action_type, proposed_payload,
              status, created_at, decided_at, actor, decided_by,
              recommendation_action, reason, decision_reason
            ) VALUES (?, ?, ?, ?, ?::jsonb, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                rec["action_id"], rec["target_type"], rec["target_id"],
                rec["action_type"], json.dumps(rec["proposed_payload"]),
                rec["status"], rec["created_at"], rec["decided_at"],
                rec["actor"], rec["decided_by"], rec["recommendation_action"],
                rec["reason"], rec["decision_reason"],
            ],
        )
        stored = _fetch(con, rec["action_id"])
    finally:
        con.close()
    return _payload("propose_action", stored)


def get_action(action_id: str, *, path: Any = None) -> dict[str, Any]:
    del path
    action_id = (action_id or "").strip()
    if not action_id:
        raise ValueError("action_id is required")
    con = db.connect()
    try:
        row = _fetch(con, action_id)
    finally:
        con.close()
    if row is None:
        raise KeyError(f"unknown action_id={action_id!r}")
    return _payload("get_action", row)


def list_actions(
    *,
    status: str | None = None,
    limit: int = 50,
    path: Any = None,
) -> dict[str, Any]:
    del path
    limit = max(1, min(int(limit), 200))
    sql = "SELECT * FROM ops.actions"
    params: list[Any] = []
    if status:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {sorted(STATUSES)}")
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    con = db.connect()
    try:
        rel = con.execute(sql, params)
        cols = [c[0] for c in rel.description]
        rows = [_row(dict(zip(cols, r))) for r in rel.fetchall()]
    finally:
        con.close()
    return _payload("list_actions", {"actions": rows, "count": len(rows)})


def _decide(
    action_id: str,
    *,
    new_status: str,
    actor: str,
    decision_reason: str | None,
    path: Any,
) -> dict[str, Any]:
    del path
    action_id = (action_id or "").strip()
    actor = (actor or "").strip() or "operator"
    if not action_id:
        raise ValueError("action_id is required")
    con = db.connect()
    try:
        current = _fetch(con, action_id)
        if current is None:
            raise KeyError(f"unknown action_id={action_id!r}")
        if current["status"] != "proposed":
            raise ValueError(
                f"action {action_id} is {current['status']}, not proposed"
            )
        con.execute(
            """
            UPDATE ops.actions
            SET status = ?, decided_at = ?, decided_by = ?, decision_reason = ?
            WHERE action_id = ?
            """,
            [new_status, _now(), actor, decision_reason, action_id],
        )
        data = _fetch(con, action_id)
    finally:
        con.close()
    tool = "approve_action" if new_status == "approved" else "reject_action"
    return _payload(tool, data)


def approve_action(
    action_id: str,
    *,
    actor: str = "operator",
    reason: str | None = None,
    path: Any = None,
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
    path: Any = None,
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
