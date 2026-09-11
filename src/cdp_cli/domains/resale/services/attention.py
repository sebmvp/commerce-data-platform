"""Attention queue and recommendation labels."""
from __future__ import annotations

from cdp_cli.db import Connection

from ..metrics import (
    ATTENTION_QUEUE_DEFAULT_LIMIT,
    HIGH_WATCH_RATE,
    STALE_LISTING_DAYS,
)
from .payload import (
    BusinessPayload,
    Provenance,
    _jsonable,
    _utcnow,
    action_for_reason,
)


def get_inventory_attention_queue(
    con: Connection,
    *,
    limit: int = ATTENTION_QUEUE_DEFAULT_LIMIT,
) -> BusinessPayload:
    """What deserves operator attention first.

    Ranking (deterministic):
      1. owned (unlisted) items by capital desc, then age desc
      2. active stale listings by age desc, then capital desc
      3. active listings with high watch_rate but no sale (engagement without conversion)

    Each row carries attention_reason + metric values used — never a bare score.
    """
    limit = max(1, min(int(limit), 200))
    rows = con.execute(
        f"""
        WITH acquisition AS (
          SELECT
            i.item_id,
            i.sku,
            i.product,
            i.status,
            i.condition,
            i.acquisition_cost_cny,
            i.target_price_usd,
            coalesce(
              min(e.event_at) FILTER (WHERE e.event_type = 'received'),
              min(e.event_at) FILTER (WHERE e.event_type = 'ordered'),
              i.created_at
            ) AS acquired_at
          FROM catalog.items i
          LEFT JOIN catalog.item_events e ON e.item_id = i.item_id
          WHERE i.status IN ('owned', 'listed')
          GROUP BY i.item_id, i.sku, i.product, i.status, i.condition,
                   i.acquisition_cost_cny, i.target_price_usd, i.created_at
        ),
        listing_roll AS (
          SELECT
            l.item_id,
            l.listing_id,
            l.status AS listing_status,
            l.listed_at,
            l.price_usd,
            ch.platform,
            date_diff('day', l.listed_at, CAST(? AS timestamp)) AS listing_age_days,
            coalesce(sum(em.views), 0) AS views,
            coalesce(sum(em.watchers), 0) AS watchers,
            coalesce(sum(em.offers), 0) AS offers,
            CASE WHEN coalesce(sum(em.views), 0) = 0 THEN NULL
                 ELSE round((sum(em.watchers)::numeric / sum(em.views)), 4)
            END AS watch_rate
          FROM sales.listings l
          LEFT JOIN core.channels ch
            ON ch.channel_key = l.channel_key
          LEFT JOIN sales.engagement_metric em ON em.listing_id = l.listing_id
          WHERE l.status = 'active'
          GROUP BY l.item_id, l.listing_id, l.status, l.listed_at, l.price_usd, ch.platform
        ),
        candidates AS (
          SELECT
            a.sku,
            a.product,
            a.status AS item_status,
            a.condition,
            a.acquisition_cost_cny,
            a.target_price_usd,
            date_diff('day', a.acquired_at, CAST(? AS timestamp)) AS inventory_age_days,
            lr.listing_id,
            lr.platform,
            lr.price_usd AS listing_price_usd,
            lr.listing_age_days,
            lr.views,
            lr.watchers,
            lr.offers,
            lr.watch_rate,
            CASE
              WHEN a.status = 'owned' THEN 'unlisted_owned'
              WHEN lr.listing_age_days >= {STALE_LISTING_DAYS} THEN 'stale_listing'
              WHEN lr.watch_rate IS NOT NULL AND lr.watch_rate >= {HIGH_WATCH_RATE}
                   AND coalesce(lr.offers, 0) = 0 THEN 'high_attention_no_offers'
              ELSE 'listed_active'
            END AS attention_reason,
            CASE
              WHEN a.status = 'owned' THEN 100
              WHEN lr.listing_age_days >= {STALE_LISTING_DAYS} THEN 80
              WHEN lr.watch_rate IS NOT NULL AND lr.watch_rate >= {HIGH_WATCH_RATE}
                   AND coalesce(lr.offers, 0) = 0 THEN 60
              ELSE 20
            END AS priority_class
          FROM acquisition a
          LEFT JOIN listing_roll lr ON lr.item_id = a.item_id
          WHERE a.status = 'owned'
             OR lr.listing_id IS NOT NULL
        )
        SELECT
          sku, product, item_status, condition,
          acquisition_cost_cny, target_price_usd, inventory_age_days,
          listing_id, platform, listing_price_usd, listing_age_days,
          views, watchers, offers, watch_rate,
          attention_reason, priority_class
        FROM candidates
        ORDER BY priority_class DESC,
                 coalesce(acquisition_cost_cny, 0) DESC,
                 coalesce(inventory_age_days, 0) DESC,
                 coalesce(listing_age_days, 0) DESC
        LIMIT ?
        """,
        [_utcnow(), _utcnow(), limit],
    ).fetchall()
    cols = [
        "sku", "product", "item_status", "condition",
        "acquisition_cost_cny", "target_price_usd", "inventory_age_days",
        "listing_id", "platform", "listing_price_usd", "listing_age_days",
        "views", "watchers", "offers", "watch_rate",
        "attention_reason", "priority_class",
    ]
    queue = [_jsonable(dict(zip(cols, r))) for r in rows]

    recommendations = []
    for row in queue[:5]:
        reason = row["attention_reason"]
        action = action_for_reason(reason)
        if reason == "unlisted_owned":
            why = (
                f"{row['sku']} is owned/unlisted with cost basis "
                f"{row['acquisition_cost_cny']} CNY and age "
                f"{row['inventory_age_days']} days — capital is idle."
            )
        elif reason == "stale_listing":
            why = (
                f"{row['sku']} active on {row['platform']} for "
                f"{row['listing_age_days']} days "
                f"(threshold {STALE_LISTING_DAYS}) without sale."
            )
        elif reason == "high_attention_no_offers":
            why = (
                f"{row['sku']} watch_rate={row['watch_rate']} with 0 offers — "
                f"attention without conversion often means price friction."
            )
        else:
            why = f"{row['sku']} is active; no urgency rule fired."
        recommendations.append(
            {
                "sku": row["sku"],
                "action": action,
                "why": why,
                "based_on": {
                    "attention_reason": reason,
                    "acquisition_cost_cny": row["acquisition_cost_cny"],
                    "inventory_age_days": row["inventory_age_days"],
                    "listing_age_days": row["listing_age_days"],
                    "watch_rate": row["watch_rate"],
                },
            }
        )

    return BusinessPayload(
        kind="recommendation",
        data={
            "queue": queue,
            "recommendations": recommendations,
            "threshold_stale_listing_days": STALE_LISTING_DAYS,
            "threshold_high_watch_rate": HIGH_WATCH_RATE,
            "ranking_notes": [
                (
                    "priority_class: unlisted_owned=100, stale_listing=80, "
                    "high_attention_no_offers=60, listed_active=20"
                ),
                "Within a class: higher capital, then older inventory/listing first",
                "RECOMMENDATION rows are heuristic; FACT rows are the queue metrics",
                f"high_attention_no_offers: watch_rate >= {HIGH_WATCH_RATE} and 0 offers",
            ],
        },
        provenance=Provenance(
            tool="get_inventory_attention_queue",
            as_of=_utcnow().isoformat(timespec="seconds") + "Z",
            source_relations=[
                "catalog.items",
                "catalog.item_events",
                "sales.listings",
                "sales.engagement_metric",
                "core.channels",
            ],
            metric_names=[
                "inventory_age_days",
                "listing_age_days",
                "stale_listing",
                "capital_tied_up_cny",
                "watch_rate",
            ],
            notes=[
                "Queue metric columns are FACT/DERIVED; 'recommendations' are labeled separately.",
                f"stale threshold = {STALE_LISTING_DAYS} days (metrics.STALE_LISTING_DAYS).",
                f"high-watch threshold = {HIGH_WATCH_RATE} (metrics.HIGH_WATCH_RATE).",
            ],
        ),
    )
