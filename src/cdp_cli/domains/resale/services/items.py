"""Item state, history, and unstructured notes."""
from __future__ import annotations

from typing import Any

from cdp_cli.db import Connection

from .payload import BusinessPayload, Provenance, _records, _utcnow


def _require_item(con: Connection, sku: str) -> dict[str, Any]:
    sku = (sku or "").strip()
    if not sku:
        raise ValueError("sku is required")
    rows = _records(
        con,
        """
        SELECT
          i.item_id, i.sku, i.product, i.variant, i.size, i.category_key,
          i.condition, i.acquisition_channel, i.acquisition_cost_cny,
          i.qty, i.status, i.target_price_usd, i.notes, i.source_file,
          i.created_at, i.updated_at,
          coalesce(
            min(e.event_at) FILTER (WHERE e.event_type = 'received'),
            min(e.event_at) FILTER (WHERE e.event_type = 'ordered'),
            i.created_at
          ) AS acquired_at,
          date_diff(
            'day',
            coalesce(
              min(e.event_at) FILTER (WHERE e.event_type = 'received'),
              min(e.event_at) FILTER (WHERE e.event_type = 'ordered'),
              i.created_at
            ),
            CAST(? AS timestamp)
          ) AS inventory_age_days
        FROM catalog.items i
        LEFT JOIN catalog.item_events e ON e.item_id = i.item_id
        WHERE i.sku = ?
        GROUP BY i.item_id, i.sku, i.product, i.variant, i.size, i.category_key,
                 i.condition, i.acquisition_channel, i.acquisition_cost_cny,
                 i.qty, i.status, i.target_price_usd, i.notes, i.source_file,
                 i.created_at, i.updated_at
        """,
        [_utcnow(), sku],
    )
    if not rows:
        raise KeyError(f"unknown item sku={sku!r}")
    return rows[0]


def _item_listings(con: Connection, item_id: str) -> list[dict[str, Any]]:
    return _records(
        con,
        """
        SELECT
          l.listing_id, l.status, l.price_usd, l.listed_at, l.sold_at,
          l.sold_price_usd, l.platform_url,
          ch.platform, ch.handle,
          CASE WHEN l.listed_at IS NULL THEN NULL
               ELSE date_diff('day', l.listed_at, CAST(? AS timestamp))
          END AS listing_age_days,
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
        WHERE l.item_id = ?
        GROUP BY l.listing_id, l.status, l.price_usd, l.listed_at, l.sold_at,
                 l.sold_price_usd, l.platform_url, ch.platform, ch.handle
        ORDER BY l.listed_at NULLS LAST
        """,
        [_utcnow(), item_id],
    )


def _item_orders(con: Connection, item_id: str) -> list[dict[str, Any]]:
    return _records(
        con,
        """
        SELECT
          order_line_key, order_id, listing_id, qty, price_usd, revenue_usd,
          fees_usd, shipping_usd, status, order_at
        FROM sales.orders
        WHERE item_id = ?
        ORDER BY order_at NULLS LAST
        """,
        [item_id],
    )

def get_item(con: Connection, sku: str) -> BusinessPayload:
    """Current state of one catalog item. Facts + named derived ages, not a recommendation."""
    item = _require_item(con, sku)
    listings = _item_listings(con, item["item_id"])
    orders = _item_orders(con, item["item_id"])
    return BusinessPayload(
        kind="fact",
        data={
            "item": item,
            "listings": listings,
            "orders": orders,
            "listing_count": len(listings),
            "order_count": len(orders),
        },
        provenance=Provenance(
            tool="get_item",
            as_of=_utcnow().isoformat(timespec="seconds") + "Z",
            source_relations=[
                "catalog.items",
                "catalog.item_events",
                "sales.listings",
                "sales.engagement_metric",
                "sales.orders",
                "core.channels",
            ],
            metric_names=["inventory_age_days", "listing_age_days", "watch_rate"],
            notes=[
                "FACT: item identity, listing rows, order rows.",
                "DERIVED: inventory_age_days, listing_age_days, watch_rate.",
                "No recommendation is attached — use get_inventory_attention_queue.",
            ],
        ),
    )


def get_item_history(con: Connection, sku: str) -> BusinessPayload:
    """Event timeline for one item: supply events, listings, engagement, orders."""
    item = _require_item(con, sku)
    item_id = item["item_id"]
    events = _records(
        con,
        """
        SELECT event_id, event_type, event_at, actor, payload_json
        FROM catalog.item_events
        WHERE item_id = ?
        ORDER BY event_at, event_id
        """,
        [item_id],
    )
    listings = _item_listings(con, item_id)
    engagement = _records(
        con,
        """
        SELECT em.listing_id, em.snapshot_at, em.views, em.watchers, em.offers
        FROM sales.engagement_metric em
        JOIN sales.listings l ON l.listing_id = em.listing_id
        WHERE l.item_id = ?
        ORDER BY em.snapshot_at, em.listing_id
        """,
        [item_id],
    )
    orders = _item_orders(con, item_id)

    timeline: list[dict[str, Any]] = []
    for ev in events:
        timeline.append(
            {
                "at": ev["event_at"],
                "type": ev["event_type"],
                "source": "catalog.item_events",
                "actor": ev["actor"],
                "detail": ev["payload_json"],
            }
        )
    for listing in listings:
        if listing.get("listed_at"):
            timeline.append(
                {
                    "at": listing["listed_at"],
                    "type": "listing_opened",
                    "source": "sales.listings",
                    "actor": None,
                    "detail": {
                        "listing_id": listing["listing_id"],
                        "platform": listing.get("platform"),
                        "price_usd": listing.get("price_usd"),
                        "status": listing.get("status"),
                    },
                }
            )
        if listing.get("sold_at"):
            timeline.append(
                {
                    "at": listing["sold_at"],
                    "type": "listing_sold",
                    "source": "sales.listings",
                    "actor": None,
                    "detail": {
                        "listing_id": listing["listing_id"],
                        "sold_price_usd": listing.get("sold_price_usd"),
                    },
                }
            )
    listing_events = _records(
        con,
        """
        SELECT le.event_id, le.listing_id, le.event_type, le.event_at,
               le.price_usd, le.status, le.payload_json, ch.platform
        FROM sales.listing_events le
        JOIN sales.listings l ON l.listing_id = le.listing_id
        LEFT JOIN core.channels ch ON ch.channel_key = l.channel_key
        WHERE l.item_id = ?
        ORDER BY le.event_at, le.event_id
        """,
        [item_id],
    )
    for ev in listing_events:
        if ev.get("event_type") in {"opened", "sold"}:
            continue
        timeline.append(
            {
                "at": ev.get("event_at"),
                "type": f"listing_{ev.get('event_type')}",
                "source": "sales.listing_events",
                "actor": None,
                "detail": {
                    "listing_id": ev.get("listing_id"),
                    "platform": ev.get("platform"),
                    "price_usd": ev.get("price_usd"),
                    "status": ev.get("status"),
                    "payload": ev.get("payload_json"),
                },
            }
        )
    for order in orders:
        timeline.append(
            {
                "at": order.get("order_at"),
                "type": "order",
                "source": "sales.orders",
                "actor": None,
                "detail": {
                    "order_id": order.get("order_id"),
                    "revenue_usd": order.get("revenue_usd"),
                    "status": order.get("status"),
                },
            }
        )
    timeline.sort(key=lambda row: (row["at"] is None, row["at"] or "", row["type"]))

    return BusinessPayload(
        kind="fact",
        data={
            "sku": item["sku"],
            "item_id": item_id,
            "status": item["status"],
            "timeline": timeline,
            "events": events,
            "listings": listings,
            "engagement": engagement,
            "orders": orders,
        },
        provenance=Provenance(
            tool="get_item_history",
            as_of=_utcnow().isoformat(timespec="seconds") + "Z",
            source_relations=[
                "catalog.items",
                "catalog.item_events",
                "sales.listings",
                "sales.listing_events",
                "sales.engagement_metric",
                "sales.orders",
            ],
            metric_names=["inventory_age_days", "listing_age_days", "watch_rate"],
            notes=[
                "Timeline merges item_events, listing open/sold, and orders.",
                "Engagement snapshots are listed separately (too dense for the spine).",
                "listing_opened/listing_sold may coincide with item_events of type listed/sold.",
            ],
        ),
    )


def search_notes(
    con: Connection,
    *,
    object_id: str | None = None,
    query: str | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Keyword search over genuinely unstructured operational notes."""
    clauses: list[str] = []
    params: list[Any] = []
    if object_id:
        clauses.append("object_id = ?")
        params.append(object_id)
    if query and query.strip():
        needle = f"%{query.strip()}%"
        clauses.append("(body ILIKE ? OR coalesce(title, '') ILIKE ?)")
        params.extend([needle, needle])
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT note_id, kind, object_type, object_id, title, body "
        f"FROM ops.notes{where} ORDER BY created_at DESC LIMIT ?"
    )
    params.append(max(1, min(int(limit), 50)))
    return _records(con, sql, params)
