"""Resale sandbox action semantics.

Generic propose/approve state lives in `cdp_cli.actions`. This module
owns listing lookup, reprice mutation, and price-review suggestions.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from ...policy import PRICE_RECOMMENDATIONS

TARGET_TYPES = frozenset({"item", "listing"})
ACTION_TYPES = frozenset(
    {"propose_list", "propose_reprice", "propose_channel_change", "mark_reviewed"}
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _event_id(*parts: Any) -> str:
    return hashlib.sha256(":".join(str(p) for p in parts).encode()).hexdigest()[:16]


def validate_action(action: dict[str, Any]) -> str | None:
    action_type = action.get("action_type")
    if action_type not in ACTION_TYPES:
        return f"unknown action_type {action_type!r}"
    target_type = action.get("target_type")
    if target_type and target_type not in TARGET_TYPES:
        return f"unknown target_type {target_type!r}"
    payload = action.get("payload") or {}
    if action_type == "propose_reprice":
        if any(key in payload for key in ("new_price_usd", "price_usd", "markdown")):
            return "numeric price is not allowed without an approved pricing policy"
        rec = (action.get("recommendation") or "").strip().upper()
        if rec and rec not in PRICE_RECOMMENDATIONS:
            return f"unknown price recommendation {action.get('recommendation')!r}"
    return None


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
    previous = {"listing_id": listing_id, "sku": sku, "price_usd": old_price}
    resulting = {
        "listing_id": listing_id,
        "sku": sku,
        "price_usd": new_price,
        "sandbox": True,
    }
    return previous, resulting


def apply_action(
    con, rec: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
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


def suggest_reprice(con, sku: str) -> dict[str, Any]:
    """Price review: evidence only. Operator supplies the sandbox price."""
    row = _active_listing(con, sku=sku, listing_id=None)
    if row is None:
        raise KeyError(f"no active listing for sku={sku!r}")
    listing_id, old_price, _status, _item_id, sku = row
    old = float(old_price)
    return {
        "action_type": "propose_reprice",
        "target_type": "listing",
        "target_id": listing_id,
        "requires_operator_price": True,
        "payload": {
            "sku": sku,
            "previous_price_usd": old,
        },
        "reason": "Price review recommended",
        "recommendation": "REVIEW_PRICE",
        "policy": {
            "id": "resale.decision.price-review",
            "version": "v1",
        },
        "evidence": {
            "listing_id": listing_id,
            "asking_price_usd": old,
            "note": (
                "No numeric markdown. Enter a sandbox price after reviewing "
                "listing age, engagement, and acquisition cost."
            ),
        },
    }
