"""Sandbox operational actions.

Recommendations suggest. A human approves or rejects. Only after approval
does the sandbox apply an internal canonical change. Nothing here calls a
marketplace API.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from . import db

ACTION_TYPES = frozenset({
    "propose_list",
    "propose_reprice",
    "propose_channel_change",
    "mark_reviewed",
})
TARGET_TYPES = frozenset({"item", "listing"})
STATUSES = frozenset({"proposed", "approved", "rejected", "applied"})

SANDBOX_FOR_REC = {
    "list_next": "propose_list",
    "review_price_or_channel": "propose_reprice",
    "consider_reprice": "propose_reprice",
    "monitor": "mark_reviewed",
}

_SANDBOX_NOTE = (
    "Sandbox only. Does not mutate any marketplace listing. "
    "Approved apply writes internal canonical history."
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds") + "Z"


def _event_id(*parts: Any) -> str:
    return hashlib.sha256(":".join(str(p) for p in parts).encode()).hexdigest()[:16]


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


def _active_listing(con, *, sku: str | None, listing_id: str | None):
    if listing_id:
        return con.execute(
            """
            SELECT l.listing_id, l.price_usd, l.status, i.item_id, i.sku
            FROM sales.listings l
            JOIN catalog.items i ON i.item_id = l.item_id
            WHERE l.listing_id = ?
            """,
            [listing_id],
        ).fetchone()
    if sku:
        return con.execute(
            """
            SELECT l.listing_id, l.price_usd, l.status, i.item_id, i.sku
            FROM sales.listings l
            JOIN catalog.items i ON i.item_id = l.item_id
            WHERE i.sku = ? AND l.status = 'active'
            ORDER BY l.listed_at DESC NULLS LAST
            LIMIT 1
            """,
            [sku],
        ).fetchone()
    return None


def _apply_reprice(con, rec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = rec.get("proposed_payload") or {}
    new_price = payload.get("new_price_usd")
    if new_price is None:
        new_price = payload.get("price_usd")
    try:
        new_price = float(new_price)
    except (TypeError, ValueError) as exc:
        raise ValueError("propose_reprice requires numeric new_price_usd") from exc
    if new_price <= 0:
        raise ValueError("new_price_usd must be positive")

    listing_id = rec["target_id"] if rec["target_type"] == "listing" else None
    sku = rec["target_id"] if rec["target_type"] == "item" else payload.get("sku")
    row = _active_listing(con, sku=sku, listing_id=listing_id)
    if row is None:
        raise ValueError("no listing found to reprice in the sandbox")
    listing_id, old_price, status, item_id, sku = row
    if old_price is None:
        raise ValueError("listing has no current price to reprice")
    old_price = float(old_price)
    if status != "active":
        raise ValueError(f"listing {listing_id} is {status}, not active")
    at = _now()
    event_id = _event_id("lev", listing_id, "price_change", rec["action_id"])
    con.execute(
        """
        INSERT INTO sales.listing_events
          (event_id, listing_id, event_type, event_at, price_usd, status, payload_json)
        VALUES (?, ?, 'price_change', ?, ?, 'active', ?::jsonb)
        ON CONFLICT (event_id) DO NOTHING
        """,
        [
            event_id,
            listing_id,
            at,
            new_price,
            json.dumps(
                {
                    "action_id": rec["action_id"],
                    "previous_price_usd": old_price,
                    "sandbox": True,
                }
            ),
        ],
    )
    con.execute(
        "UPDATE sales.listings SET price_usd = ?, updated_at = ? WHERE listing_id = ?",
        [new_price, at, listing_id],
    )
    item_event_id = _event_id("event", item_id, "price_change", rec["action_id"])
    con.execute(
        """
        INSERT INTO catalog.item_events
          (event_id, item_id, event_type, event_at, actor, payload_json)
        VALUES (?, ?, 'price_change', ?, ?, ?::jsonb)
        ON CONFLICT (event_id) DO NOTHING
        """,
        [
            item_event_id,
            item_id,
            at,
            rec.get("decided_by") or rec.get("actor") or "operator",
            json.dumps(
                {
                    "action_id": rec["action_id"],
                    "listing_id": listing_id,
                    "previous_price_usd": old_price,
                    "new_price_usd": new_price,
                    "sandbox": True,
                }
            ),
        ],
    )
    previous = {
        "listing_id": listing_id,
        "sku": sku,
        "price_usd": old_price,
    }
    resulting = {
        "listing_id": listing_id,
        "sku": sku,
        "price_usd": new_price,
        "sandbox": True,
    }
    return previous, resulting


def _apply(con, rec: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    action_type = rec["action_type"]
    if action_type == "propose_reprice":
        return _apply_reprice(con, rec)
    if action_type in {"mark_reviewed", "propose_list", "propose_channel_change"}:
        return None, {
            "sandbox": True,
            "mutated": False,
            "note": "No catalog mutation for this action type.",
        }
    raise ValueError(f"cannot apply action_type {action_type}")


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
            from .business import capture_business_snapshot

            capture_business_snapshot(con, trigger="action_apply")
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
    try:
        return SANDBOX_FOR_REC[rec_action]
    except KeyError as e:
        raise ValueError(f"unknown recommendation action {rec_action!r}") from e


def suggest_reprice(con, sku: str) -> dict[str, Any]:
    """Build a sandbox reprice proposal from the current active listing."""
    row = _active_listing(con, sku=sku, listing_id=None)
    if row is None:
        raise KeyError(f"no active listing for sku={sku!r}")
    listing_id, old_price, _status, _item_id, sku = row
    old = float(old_price)
    proposed = round(old * 0.89, 2)
    if proposed >= old:
        proposed = round(max(old - 1, 0.01), 2)
    return {
        "action_type": "propose_reprice",
        "target_type": "listing",
        "target_id": listing_id,
        "payload": {
            "sku": sku,
            "previous_price_usd": old,
            "new_price_usd": proposed,
        },
        "reason": f"Sandbox reprice {old} -> {proposed} (internal only)",
        "evidence": {
            "listing_id": listing_id,
            "asking_price_usd": old,
            "suggested_price_usd": proposed,
        },
    }
