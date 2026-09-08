"""Labeled attention-queue eval.

Sample-data tests prove the tool runs. This file locks the *policy*:
class order, intra-class sort, thresholds, action mapping, and the
FACT vs RECOMMENDATION split. Cases use a private warehouse so ranking
cannot drift with the public fixture.

Changing ranking here is a product decision, not a silent refactor.
"""
from __future__ import annotations

from cdp_cli import metrics
from cdp_cli.business import get_inventory_attention_queue

# SKUs are the eval IDs. Keep them stable; tests assert on these names.
CAPITAL_HIGH = "eval-capital-high"
CAPITAL_LOW = "eval-capital-low"
AGE_OLD = "eval-age-old"
AGE_NEW = "eval-age-new"
STALE = "eval-stale"
ALMOST_STALE = "eval-almost-stale"
WATCH_NO_OFFER = "eval-watch-no-offer"
WATCH_WITH_OFFER = "eval-watch-with-offer"
WATCH_BELOW = "eval-watch-below"
NO_VIEWS = "eval-no-views"
SOLD = "eval-sold"


def _seed(con) -> None:
    """Minimal world covering every attention class and a few boundaries."""
    con.execute(
        """
        INSERT INTO core.channels
          (channel_key, platform, handle, standing, fee_pct, valid_from)
        VALUES ('grailed/eval@0', 'grailed', 'eval', 'active', 0.09,
                TIMESTAMP '2020-01-01')
        """
    )

    def item(sku: str, status: str, cost: float, age_days: int) -> str:
        item_id = sku
        con.execute(
            """
            INSERT INTO catalog.items
              (item_id, sku, product, acquisition_cost_cny, status, qty)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            [item_id, sku, sku, cost, status],
        )
        con.execute(
            """
            INSERT INTO catalog.item_events
              (event_id, item_id, event_type, event_at)
            VALUES (?, ?, 'received',
                    current_timestamp - (CAST(? AS INTEGER) * INTERVAL '1' DAY))
            """,
            [f"ev-{sku}", item_id, age_days],
        )
        return item_id

    def listing(sku: str, age_days: int, views: int, watchers: int, offers: int) -> None:
        listing_id = f"lst-{sku}"
        con.execute(
            """
            INSERT INTO sales.listings
              (listing_id, item_id, channel_key, price_usd, status, listed_at)
            VALUES (?, ?, 'grailed/eval@0', 100, 'active',
                    current_timestamp - (CAST(? AS INTEGER) * INTERVAL '1' DAY))
            """,
            [listing_id, sku, age_days],
        )
        con.execute(
            """
            INSERT INTO sales.engagement_metric
              (metric_id, listing_id, snapshot_at, views, watchers, offers)
            VALUES (?, ?, DATE '2026-01-01', ?, ?, ?)
            """,
            [f"em-{sku}", listing_id, views, watchers, offers],
        )

    item(CAPITAL_HIGH, "owned", 9000, 10)
    item(CAPITAL_LOW, "owned", 1000, 400)
    item(AGE_OLD, "owned", 500, 300)
    item(AGE_NEW, "owned", 500, 10)

    item(STALE, "listed", 200, 40)
    listing(STALE, 20, 10, 1, 0)

    item(ALMOST_STALE, "listed", 200, 40)
    listing(ALMOST_STALE, 13, 10, 0, 0)

    item(WATCH_NO_OFFER, "listed", 200, 20)
    listing(WATCH_NO_OFFER, 5, 100, 8, 0)  # watch_rate = 0.08

    item(WATCH_WITH_OFFER, "listed", 200, 20)
    listing(WATCH_WITH_OFFER, 5, 100, 10, 2)

    item(WATCH_BELOW, "listed", 200, 20)
    listing(WATCH_BELOW, 5, 100, 7, 0)  # 0.07 < HIGH_WATCH_RATE

    item(NO_VIEWS, "listed", 200, 20)
    listing(NO_VIEWS, 5, 0, 0, 0)

    item(SOLD, "sold", 8000, 5)


def _by_sku(queue: list[dict]) -> dict[str, dict]:
    return {row["sku"]: row for row in queue}


def _rank(queue: list[dict], sku: str) -> int:
    for i, row in enumerate(queue):
        if row["sku"] == sku:
            return i
    raise AssertionError(f"{sku} missing from attention queue")


def test_attention_eval_class_order_and_exclusions(warehouse):
    _seed(warehouse)
    payload = get_inventory_attention_queue(warehouse, limit=50)
    assert payload.kind == "recommendation"
    queue = payload.data["queue"]
    skus = [r["sku"] for r in queue]

    assert SOLD not in skus
    assert payload.data["threshold_stale_listing_days"] == metrics.STALE_LISTING_DAYS
    assert payload.data["threshold_high_watch_rate"] == metrics.HIGH_WATCH_RATE

    # Class order: unlisted (100) → stale (80) → high watch / 0 offers (60)
    # → remaining active (20).
    assert _rank(queue, CAPITAL_HIGH) < _rank(queue, STALE)
    assert _rank(queue, STALE) < _rank(queue, WATCH_NO_OFFER)
    assert _rank(queue, WATCH_NO_OFFER) < _rank(queue, ALMOST_STALE)

    by = _by_sku(queue)
    assert by[CAPITAL_HIGH]["attention_reason"] == "unlisted_owned"
    assert by[STALE]["attention_reason"] == "stale_listing"
    assert by[WATCH_NO_OFFER]["attention_reason"] == "high_attention_no_offers"
    assert by[ALMOST_STALE]["attention_reason"] == "listed_active"
    assert by[WATCH_WITH_OFFER]["attention_reason"] == "listed_active"
    assert by[WATCH_BELOW]["attention_reason"] == "listed_active"
    assert by[NO_VIEWS]["attention_reason"] == "listed_active"
    assert by[NO_VIEWS]["watch_rate"] is None


def test_attention_eval_unlisted_sorts_capital_then_age(warehouse):
    _seed(warehouse)
    queue = get_inventory_attention_queue(warehouse, limit=50).data["queue"]
    # Higher cost basis beats older-but-cheaper inventory.
    assert _rank(queue, CAPITAL_HIGH) < _rank(queue, CAPITAL_LOW)
    # Equal cost: older first.
    assert _rank(queue, AGE_OLD) < _rank(queue, AGE_NEW)
    assert _rank(queue, CAPITAL_LOW) < _rank(queue, AGE_OLD)


def test_attention_eval_stale_threshold_is_inclusive(warehouse):
    _seed(warehouse)
    by = _by_sku(get_inventory_attention_queue(warehouse, limit=50).data["queue"])
    assert by[STALE]["listing_age_days"] >= metrics.STALE_LISTING_DAYS
    assert by[ALMOST_STALE]["listing_age_days"] == 13
    assert by[ALMOST_STALE]["listing_age_days"] < metrics.STALE_LISTING_DAYS


def test_attention_eval_watch_rate_boundary(warehouse):
    _seed(warehouse)
    by = _by_sku(get_inventory_attention_queue(warehouse, limit=50).data["queue"])
    assert by[WATCH_NO_OFFER]["watch_rate"] == metrics.HIGH_WATCH_RATE
    assert by[WATCH_NO_OFFER]["offers"] == 0
    assert by[WATCH_BELOW]["watch_rate"] < metrics.HIGH_WATCH_RATE
    assert by[WATCH_WITH_OFFER]["watch_rate"] > metrics.HIGH_WATCH_RATE
    assert by[WATCH_WITH_OFFER]["offers"] > 0


def test_attention_eval_actions_and_layer_split(warehouse):
    """Recommendations are the top of the ranked queue, not a second ranking."""
    _seed(warehouse)
    payload = get_inventory_attention_queue(warehouse, limit=50)
    queue = payload.data["queue"]
    recs = payload.data["recommendations"]
    expected = {
        "unlisted_owned": "list_next",
        "stale_listing": "review_price_or_channel",
        "high_attention_no_offers": "consider_reprice",
        "listed_active": "monitor",
    }
    assert [r["sku"] for r in recs] == [r["sku"] for r in queue[:5]]
    for rec, row in zip(recs, queue[:5]):
        assert rec["action"] == expected[row["attention_reason"]]
        assert rec["based_on"]["attention_reason"] == row["attention_reason"]
        assert "action" not in rec["based_on"]
        assert "margin" not in str(rec).lower()
    for row in queue:
        assert "action" not in row
        assert "why" not in row
    rec_by_sku = {r["sku"]: r for r in recs}
    assert rec_by_sku[CAPITAL_HIGH]["action"] == "list_next"
    assert rec_by_sku[STALE]["action"] == "review_price_or_channel"


def test_attention_eval_emits_consider_reprice(warehouse):
    """Need the watch-no-offer SKU inside the top-5 recommendation window."""
    _seed(warehouse)
    warehouse.execute("DELETE FROM catalog.items WHERE status = 'owned'")
    recs = {
        r["sku"]: r
        for r in get_inventory_attention_queue(warehouse, limit=50).data["recommendations"]
    }
    assert recs[WATCH_NO_OFFER]["action"] == "consider_reprice"
    assert recs[STALE]["action"] == "review_price_or_channel"
