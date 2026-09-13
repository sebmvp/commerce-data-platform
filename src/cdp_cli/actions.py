"""Sandbox operational actions — generic propose/approve state machine.

Domain-specific application (what a reprice does) lives on the active
Domain.apply_action hook. Nothing here calls a marketplace API.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from . import db
from .core.domain import get_active_domain

STATUSES = frozenset({"proposed", "approved", "rejected", "applied"})

_SANDBOX_NOTE = (
    "Sandbox only. Does not mutate any marketplace listing. "
    "Approved apply writes internal canonical history."
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds") + "Z"


def _row(rec: dict[str, Any]) -> dict[str, Any]:
    for key in ("proposed_payload", "supporting_context", "previous_value", "resulting_value"):
        val = rec.get(key)
        if isinstance(val, str):
            try:
                rec[key] = json.loads(val)
            except json.JSONDecodeError:
                pass
    for key in ("created_at", "decided_at", "applied_at"):
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
                "ACTION is proposed/approved operational intent, not a catalog fact until applied.",
                _SANDBOX_NOTE,
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
    supporting_context: dict[str, Any] | None = None,
    context_question: str | None = None,
    path: Any = None,
) -> dict[str, Any]:
    del path
    target_type = (target_type or "").strip()
    target_id = (target_id or "").strip()
    action_type = (action_type or "").strip()
    actor = (actor or "").strip() or "operator"
    reason = (reason or "").strip()
    domain = get_active_domain()
    allowed_targets = domain.target_types
    allowed_actions = domain.action_types
    if allowed_targets and target_type not in allowed_targets:
        raise ValueError(f"target_type must be one of {sorted(allowed_targets)}")
    if not target_id:
        raise ValueError("target_id is required")
    if allowed_actions and action_type not in allowed_actions:
        raise ValueError(f"action_type must be one of {sorted(allowed_actions)}")
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
        "actor": actor,
        "recommendation_action": recommendation_action,
        "reason": reason,
        "supporting_context": supporting_context,
        "context_question": context_question,
    }
    con = db.connect()
    try:
        con.execute(
            """
            INSERT INTO ops.actions (
              action_id, target_type, target_id, action_type, proposed_payload,
              status, created_at, actor, recommendation_action, reason,
              supporting_context, context_question
            ) VALUES (?, ?, ?, ?, ?::jsonb, ?, ?, ?, ?, ?, ?::jsonb, ?)
            """,
            [
                rec["action_id"], rec["target_type"], rec["target_id"],
                rec["action_type"], json.dumps(rec["proposed_payload"]),
                rec["status"], rec["created_at"], rec["actor"],
                rec["recommendation_action"], rec["reason"],
                json.dumps(rec["supporting_context"]) if rec["supporting_context"] is not None else None,
                rec["context_question"],
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
    target_id: str | None = None,
    limit: int = 50,
    path: Any = None,
) -> dict[str, Any]:
    del path
    limit = max(1, min(int(limit), 200))
    sql = "SELECT * FROM ops.actions"
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {sorted(STATUSES)}")
        clauses.append("status = ?")
        params.append(status)
    if target_id:
        clauses.append("target_id = ?")
        params.append(target_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
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


def _apply(con, rec: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    return get_active_domain().apply_action(con, rec)


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
        con.execute("BEGIN")
        current = _fetch(con, action_id)
        if current is None:
            raise KeyError(f"unknown action_id={action_id!r}")
        if current["status"] != "proposed":
            raise ValueError(
                f"action {action_id} is {current['status']}, not proposed"
            )
        decided = _now()
        con.execute(
            """
            UPDATE ops.actions
            SET status = ?, decided_at = ?, decided_by = ?, decision_reason = ?
            WHERE action_id = ?
            """,
            [new_status, decided, actor, decision_reason, action_id],
        )
        if new_status == "approved":
            approved = _fetch(con, action_id)
            assert approved is not None
            previous, resulting = _apply(con, approved)
            con.execute(
                """
                UPDATE ops.actions
                SET status = 'applied', applied_at = ?,
                    previous_value = ?::jsonb, resulting_value = ?::jsonb
                WHERE action_id = ?
                """,
                [
                    _now(),
                    json.dumps(previous) if previous is not None else None,
                    json.dumps(resulting) if resulting is not None else None,
                    action_id,
                ],
            )
            get_active_domain().on_action_applied(con)
        data = _fetch(con, action_id)
        con.execute("COMMIT")
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise
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
    return get_active_domain().sandbox_type_for_recommendation(rec_action)
