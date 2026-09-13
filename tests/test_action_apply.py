"""Sandbox action apply mutates internal canonical history only."""
from __future__ import annotations

from datetime import datetime

import pytest

from cdp_cli import actions
from cdp_cli.core import assemble_context
from cdp_cli.domains.resale.actions import suggest_reprice
from cdp_cli.domains.resale.services import (
    get_item,
    get_item_history,
    get_listing_as_of,
)


def _seed_listed_item(con, sku: str = "reprice-loop-s", price: float = 145.0) -> None:
    con.execute(
        """
        INSERT INTO catalog.items (item_id, sku, product, status, acquisition_cost_cny)
        VALUES (?, ?, 'Loop Tee', 'listed', 62)
        """,
        [f"item-{sku}", sku],
    )
    con.execute(
        """
        INSERT INTO core.channels
          (channel_key, platform, handle, standing, fee_pct, valid_from)
        VALUES ('grailed/loop@2025', 'grailed', 'loop', 'active', 0.09, '2025-01-01')
        """
    )
    listed_at = datetime(2026, 8, 1, 12, 0, 0)
    con.execute(
        """
        INSERT INTO sales.listings
          (listing_id, item_id, channel_key, price_usd, status, listed_at)
        VALUES (?, ?, 'grailed/loop@2025', ?, 'active', ?)
        """,
        [f"lst-{sku}", f"item-{sku}", price, listed_at],
    )
    con.execute(
        """
        INSERT INTO sales.listing_events
          (event_id, listing_id, event_type, event_at, price_usd, status)
        VALUES (?, ?, 'opened', ?, ?, 'active')
        """,
        [f"lev-open-{sku}", f"lst-{sku}", listed_at, price],
    )


def test_reprice_apply_changes_listing_and_history(warehouse):
    _seed_listed_item(warehouse)
    proposed = actions.propose(
        target_type="item",
        target_id="reprice-loop-s",
        action_type="propose_reprice",
        reason="stale listing sandbox",
        payload={"sku": "reprice-loop-s", "new_price_usd": 129.0},
    )
    assert proposed["data"]["status"] == "proposed"
    applied = actions.approve_action(proposed["data"]["action_id"], actor="operator")
    rec = applied["data"]
    assert rec["status"] == "applied"
    assert rec["applied_at"]
    assert rec["previous_value"]["price_usd"] == 145.0
    assert rec["resulting_value"]["price_usd"] == 129.0

    item = get_item(warehouse, "reprice-loop-s")
    listing = item.data["listings"][0]
    assert listing["price_usd"] == 129.0

    history = get_item_history(warehouse, "reprice-loop-s")
    types = [row["type"] for row in history.data["timeline"]]
    assert "listing_price_change" in types

    before = get_listing_as_of(
        warehouse, "reprice-loop-s", as_of="2026-08-15T00:00:00"
    )
    assert before.data["listings"][0]["price_usd"] == 145.0


def test_reprice_is_visible_to_context_engine(warehouse):
    _seed_listed_item(warehouse, sku="ctx-loop-s", price=200.0)
    proposed = actions.propose(
        target_type="item",
        target_id="ctx-loop-s",
        action_type="propose_reprice",
        reason="test",
        payload={"sku": "ctx-loop-s", "new_price_usd": 175.0},
    )
    actions.approve_action(proposed["data"]["action_id"])
    bundle = assemble_context(
        warehouse,
        question="Should I reprice ctx-loop-s?",
        intent="reprice_item",
        sku="ctx-loop-s",
    )
    assert bundle.metrics.get("asking_price_usd") == 175.0


def test_cannot_approve_twice(warehouse):
    proposed = actions.propose(
        target_type="item",
        target_id="stone-cargo-l",
        action_type="mark_reviewed",
        reason="looked at it",
    )
    actions.approve_action(proposed["data"]["action_id"])
    with pytest.raises(ValueError, match="applied"):
        actions.approve_action(proposed["data"]["action_id"])


def test_reject_does_not_mutate(warehouse):
    _seed_listed_item(warehouse, sku="reject-loop-s", price=90.0)
    proposed = actions.propose(
        target_type="item",
        target_id="reject-loop-s",
        action_type="propose_reprice",
        reason="no",
        payload={"sku": "reject-loop-s", "new_price_usd": 70.0},
    )
    rejected = actions.reject_action(proposed["data"]["action_id"], reason="not now")
    assert rejected["data"]["status"] == "rejected"
    item = get_item(warehouse, "reject-loop-s")
    assert item.data["listings"][0]["price_usd"] == 90.0


def test_suggest_reprice_does_not_invent_a_markdown(warehouse):
    _seed_listed_item(warehouse, sku="review-s", price=200.0)
    suggestion = suggest_reprice(warehouse, "review-s")
    assert suggestion["requires_operator_price"] is True
    assert "new_price_usd" not in suggestion["payload"]
    assert suggestion["payload"]["previous_price_usd"] == 200.0
    assert "review" in suggestion["reason"].lower()

