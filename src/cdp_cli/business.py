"""Typed business query layer — deterministic answers with provenance.

This is the AI-ready tool surface *without* an LLM. Every function returns
structured facts plus enough metadata for a later copilot to cite evidence.

FACT vs DERIVED vs RECOMMENDATION are labeled explicitly in payloads.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal

from . import metrics as M
from .db import Connection
from .observability import trust_report

Kind = Literal["fact", "derived", "recommendation"]

# Recommendation policy. Queue rows stay facts; these labels are heuristic.
ACTION_FOR_REASON = {
    "unlisted_owned": "list_next",
    "stale_listing": "review_price_or_channel",
    "high_attention_no_offers": "consider_reprice",
    "listed_active": "monitor",
}


def action_for_reason(reason: str) -> str:
    return ACTION_FOR_REASON.get(reason, "monitor")


def _utcnow() -> datetime:
    from .clock import reference_now

    return reference_now()


def _parse_as_of(as_of: datetime | date | str | None) -> datetime:
    """Accept ISO timestamps (with optional Z) or a date; default now."""
    if as_of is None:
        return _utcnow()
    if isinstance(as_of, datetime):
        if as_of.tzinfo:
            return as_of.astimezone(UTC).replace(tzinfo=None)
        return as_of
    if isinstance(as_of, date):
        return datetime(as_of.year, as_of.month, as_of.day)
    text = str(as_of).strip()
    if not text:
        raise ValueError("as_of is empty")
    text = text.removesuffix("Z")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as e:
        raise ValueError(f"invalid as_of {as_of!r}; expected ISO-8601") from e
    if isinstance(parsed, datetime):
        if parsed.tzinfo:
            return parsed.astimezone(UTC).replace(tzinfo=None)
        return parsed
    return datetime(parsed.year, parsed.month, parsed.day)


@dataclass
class Provenance:
    tool: str
    as_of: str
    source_relations: list[str]
    metric_names: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BusinessPayload:
    kind: Kind
    data: Any
    provenance: Provenance

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "data": self.data,
            "provenance": self.provenance.to_dict(),
        }


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _records(
    con: Connection, sql: str, params: list | None = None
) -> list[dict[str, Any]]:
    rel = con.execute(sql, params or [])
    cols = [c[0] for c in rel.description]
    out: list[dict[str, Any]] = []
    for row in rel.fetchall():
        rec: dict[str, Any] = {}
        for col, val in zip(cols, row):
            if col in {"payload_json", "raw_json"} and isinstance(val, str):
                try:
                    val = json.loads(val)
                except json.JSONDecodeError:
                    pass
            rec[col] = _jsonable(val)
        out.append(rec)
    return out


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


def get_business_snapshot(con: Connection) -> BusinessPayload:
    """Current resale operation state — counts + capital, not a recommendation."""
    items = con.execute(
        """
        SELECT
          count(*) FILTER (WHERE status = 'owned')   AS owned_unlisted,
          count(*) FILTER (WHERE status = 'listed')  AS listed_items,
          count(*) FILTER (WHERE status = 'sold')    AS sold_items,
          count(*) FILTER (WHERE status IN ('owned','listed')) AS capital_items,
          coalesce(sum(acquisition_cost_cny)
                   FILTER (WHERE status IN ('owned','listed')), 0) AS capital_tied_up_cny,
          count(*) AS items_total
        FROM catalog.items
        """
    ).fetchone()
    listings = con.execute(
        """
        SELECT
          count(*) FILTER (WHERE status = 'active') AS active_listings,
          count(*) FILTER (
            WHERE status = 'active'
              AND listed_at IS NOT NULL
              AND date_diff('day', listed_at, CAST(? AS timestamp)) >= ?
          ) AS stale_active_listings
        FROM sales.listings
        """,
        [_utcnow(), M.STALE_LISTING_DAYS],
    ).fetchone()
    orders = con.execute(
        """
        SELECT
          count(*) FILTER (WHERE status != 'cancelled') AS orders,
          coalesce(sum(revenue_usd) FILTER (WHERE status != 'cancelled'), 0) AS realized_revenue_usd,
          coalesce(sum(revenue_usd - coalesce(fees_usd,0) - coalesce(shipping_usd,0))
                   FILTER (WHERE status != 'cancelled'), 0) AS realized_gross_after_fees_usd
        FROM sales.orders
        """
    ).fetchone()
    trust = trust_report(con)

    data = {
        "owned_unlisted": int(items[0] or 0),
        "listed_items": int(items[1] or 0),
        "sold_items": int(items[2] or 0),
        "capital_items": int(items[3] or 0),
        "capital_tied_up_cny": float(items[4] or 0),
        "capital_tied_up_usd_est": round(float(items[4] or 0) * M.CNY_TO_USD_EST, 2),
        "items_total": int(items[5] or 0),
        "active_listings": int(listings[0] or 0),
        "stale_active_listings": int(listings[1] or 0),
        "stale_listing_days_threshold": M.STALE_LISTING_DAYS,
        "orders": int(orders[0] or 0),
        "realized_revenue_usd": float(orders[1] or 0),
        "realized_gross_after_fees_usd": float(orders[2] or 0),
        "warehouse_trust_ok": trust.ok,
        "warehouse_trust_reasons": list(trust.reasons),
        "fx_note": f"USD estimate uses CNY_TO_USD_EST={M.CNY_TO_USD_EST} display rate only",
    }
    return BusinessPayload(
        kind="derived",
        data=data,
        provenance=Provenance(
            tool="get_business_snapshot",
            as_of=_utcnow().isoformat(timespec="seconds") + "Z",
            source_relations=[
                "catalog.items",
                "sales.listings",
                "sales.orders",
                "core.ingest_runs",
            ],
            metric_names=[
                "capital_tied_up_cny",
                "unlisted_owned_count",
                "stale_listing",
                "realized_revenue_usd",
                "realized_gross_after_fees_usd",
            ],
            notes=[
                "FACT: row counts from current projections.",
                "DERIVED: capital sums, stale counts, fee-adjusted gross.",
                "realized_gross_after_fees_usd is NOT full margin (excludes acquisition cost).",
            ],
        ),
    )


def get_inventory_attention_queue(
    con: Connection,
    *,
    limit: int = M.ATTENTION_QUEUE_DEFAULT_LIMIT,
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
              WHEN lr.listing_age_days >= {M.STALE_LISTING_DAYS} THEN 'stale_listing'
              WHEN lr.watch_rate IS NOT NULL AND lr.watch_rate >= {M.HIGH_WATCH_RATE}
                   AND coalesce(lr.offers, 0) = 0 THEN 'high_attention_no_offers'
              ELSE 'listed_active'
            END AS attention_reason,
            CASE
              WHEN a.status = 'owned' THEN 100
              WHEN lr.listing_age_days >= {M.STALE_LISTING_DAYS} THEN 80
              WHEN lr.watch_rate IS NOT NULL AND lr.watch_rate >= {M.HIGH_WATCH_RATE}
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
                f"(threshold {M.STALE_LISTING_DAYS}) without sale."
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
            "threshold_stale_listing_days": M.STALE_LISTING_DAYS,
            "threshold_high_watch_rate": M.HIGH_WATCH_RATE,
            "ranking_notes": [
                (
                    "priority_class: unlisted_owned=100, stale_listing=80, "
                    "high_attention_no_offers=60, listed_active=20"
                ),
                "Within a class: higher capital, then older inventory/listing first",
                "RECOMMENDATION rows are heuristic; FACT rows are the queue metrics",
                f"high_attention_no_offers: watch_rate >= {M.HIGH_WATCH_RATE} and 0 offers",
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
                f"stale threshold = {M.STALE_LISTING_DAYS} days (metrics.STALE_LISTING_DAYS).",
                f"high-watch threshold = {M.HIGH_WATCH_RATE} (metrics.HIGH_WATCH_RATE).",
            ],
        ),
    )


def get_ingest_health(con: Connection) -> BusinessPayload:
    from .observability import trust_report as tr

    report = tr(con)
    return BusinessPayload(
        kind="fact",
        data=report.to_dict(),
        provenance=Provenance(
            tool="get_ingest_health",
            as_of=_utcnow().isoformat(timespec="seconds") + "Z",
            source_relations=["core.ingest_runs", "core.rejected_records"],
            metric_names=[],
            notes=["Trust ok=false means integrity alarm (orphan or unbalanced success)."],
        ),
    )


def explain_metric(name: str) -> BusinessPayload:
    m = M.get_metric(name)
    return BusinessPayload(
        kind="fact",
        data={
            "name": m.name,
            "definition": m.definition,
            "grain": m.grain,
            "required_fields": list(m.required_fields),
            "null_behavior": m.null_behavior,
            "temporal": m.temporal,
            "unit": m.unit,
            "limitations": m.limitations,
        },
        provenance=Provenance(
            tool="explain_metric",
            as_of=_utcnow().isoformat(timespec="seconds") + "Z",
            source_relations=["cdp_cli.metrics.METRICS"],
            metric_names=[m.name],
            notes=["Canonical definition registry — not inferred from SQL ad hoc."],
        ),
    )


def get_channel_as_of(
    con: Connection,
    platform: str,
    *,
    as_of: datetime | date | str | None = None,
    handle: str | None = None,
) -> BusinessPayload:
    """Channel version(s) covering as_of. FACT — not a fee recommendation.

    SCD-2 intervals are half-open [valid_from, valid_to). A row with
    valid_to NULL is current. Listing.channel_key is the version stamped
    at ingest, which may differ from the version that covered listed_at.
    """
    platform = (platform or "").strip()
    if not platform:
        raise ValueError("platform is required")
    handle = (handle or "").strip() or None
    at = _parse_as_of(as_of)

    exists_sql = "SELECT 1 FROM core.channels WHERE platform = ?"
    exists_params: list[Any] = [platform]
    if handle:
        exists_sql += " AND handle = ?"
        exists_params.append(handle)
    exists_sql += " LIMIT 1"
    if not con.execute(exists_sql, exists_params).fetchone():
        label = f"{platform}/{handle}" if handle else platform
        raise KeyError(f"unknown channel platform={label!r}")

    sql = """
        SELECT channel_key, platform, handle, standing, region, fee_pct,
               valid_from, valid_to
        FROM core.channels
        WHERE platform = ?
          AND valid_from <= ?
          AND (valid_to IS NULL OR valid_to > ?)
    """
    params: list[Any] = [platform, at, at]
    if handle:
        sql += " AND handle = ?"
        params.append(handle)
    sql += " ORDER BY handle, valid_from"
    versions = _records(con, sql, params)

    return BusinessPayload(
        kind="fact",
        data={
            "platform": platform,
            "handle": handle,
            "as_of": at.isoformat(timespec="seconds"),
            "interval": "[valid_from, valid_to)",
            "versions": versions,
            "covered": bool(versions),
        },
        provenance=Provenance(
            tool="get_channel_as_of",
            as_of=at.isoformat(timespec="seconds") + "Z",
            source_relations=["core.channels"],
            metric_names=[],
            notes=[
                "FACT: SCD-2 row covering as_of; fee_pct is that version's rate.",
                "Interval is [valid_from, valid_to). The boundary instant belongs to the newer version.",
                "Does not compute order fees. Sample orders may use a generator rate that disagrees with this version.",
            ],
        ),
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


def get_listing_as_of(
    con: Connection,
    sku: str,
    as_of: datetime | date | str | None = None,
) -> BusinessPayload:
    """Listing projection at as_of from listing_events (fallback: listing row)."""
    at = _parse_as_of(as_of)
    item = _require_item(con, sku)
    states = _records(
        con,
        """
        WITH ranked AS (
          SELECT
            le.listing_id, le.event_type, le.event_at, le.price_usd, le.status,
            ch.platform,
            row_number() OVER (
              PARTITION BY le.listing_id
              ORDER BY le.event_at DESC, le.event_id DESC
            ) AS rn
          FROM sales.listing_events le
          JOIN sales.listings l ON l.listing_id = le.listing_id
          JOIN catalog.items i ON i.item_id = l.item_id
          LEFT JOIN core.channels ch ON ch.channel_key = l.channel_key
          WHERE i.sku = ? AND le.event_at <= ?
        )
        SELECT listing_id, platform, event_type, event_at, price_usd, status
        FROM ranked WHERE rn = 1
        ORDER BY event_at
        """,
        [sku, at],
    )
    if not states:
        states = _records(
            con,
            """
            SELECT l.listing_id, ch.platform, l.status, l.price_usd,
                   l.listed_at AS event_at, 'opened' AS event_type
            FROM sales.listings l
            JOIN catalog.items i ON i.item_id = l.item_id
            LEFT JOIN core.channels ch ON ch.channel_key = l.channel_key
            WHERE i.sku = ?
              AND l.listed_at IS NOT NULL AND l.listed_at <= ?
              AND (l.sold_at IS NULL OR l.sold_at > ?)
            """,
            [sku, at, at],
        )
    return BusinessPayload(
        kind="fact",
        data={
            "sku": sku,
            "as_of": at.isoformat(timespec="seconds"),
            "listings": states,
            "covered": bool(states),
            "item_status_now": item.get("status"),
        },
        provenance=Provenance(
            tool="get_listing_as_of",
            as_of=at.isoformat(timespec="seconds") + "Z",
            source_relations=["sales.listing_events", "sales.listings", "catalog.items"],
            notes=[
                "FACT: latest listing_event at or before as_of per listing.",
                "Falls back to listing.listed_at/sold_at if no events exist.",
            ],
        ),
    )


def get_channel_comparison(con: Connection) -> BusinessPayload:
    """Deterministic channel stats + unlisted capital. Not a 'best channel' score."""
    channels = _records(
        con,
        """
        SELECT
          ch.platform,
          count(*) AS listings,
          count(*) FILTER (WHERE l.status = 'sold') AS sold,
          round(
            (count(*) FILTER (WHERE l.status = 'sold')::numeric
             / nullif(count(*), 0)), 3
          ) AS sell_through_rate,
          round(avg(
            CASE WHEN l.sold_at IS NOT NULL AND l.listed_at IS NOT NULL
                 THEN extract(epoch from (l.sold_at - l.listed_at)) / 86400.0
            END
          )::numeric, 1) AS avg_days_to_sale,
          round(sum(l.sold_price_usd)::numeric, 2) AS gross_sales_usd,
          (
            SELECT c2.fee_pct FROM core.channels c2
            WHERE c2.platform = ch.platform AND c2.valid_to IS NULL
            LIMIT 1
          ) AS current_fee_pct
        FROM sales.listings l
        LEFT JOIN core.channels ch ON ch.channel_key = l.channel_key
        GROUP BY ch.platform
        ORDER BY ch.platform
        """,
    )
    unlisted = _records(
        con,
        """
        SELECT sku, product, acquisition_cost_cny, status
        FROM catalog.items
        WHERE status = 'owned'
        ORDER BY coalesce(acquisition_cost_cny, 0) DESC
        """,
    )
    capital = sum(float(r["acquisition_cost_cny"] or 0) for r in unlisted)
    return BusinessPayload(
        kind="derived",
        data={
            "channels": channels,
            "unlisted_owned": unlisted,
            "unlisted_count": len(unlisted),
            "capital_tied_up_cny": capital,
        },
        provenance=Provenance(
            tool="get_channel_comparison",
            as_of=_utcnow().isoformat(timespec="seconds") + "Z",
            source_relations=["sales.listings", "core.channels", "catalog.items"],
            metric_names=["sell_through_rate", "avg_days_to_sale", "capital_tied_up_cny"],
            notes=[
                "DERIVED from sold listings and current fee versions.",
                "Does not pick a 'best' channel — it reports evidence.",
                "realized gross is not margin.",
            ],
        ),
    )


def get_listing_performance(con: Connection, *, limit: int = 50) -> BusinessPayload:
    """Active listing engagement vs offers. FACT/DERIVED, not a reprice order."""
    limit = max(1, min(int(limit), 200))
    rows = _records(
        con,
        """
        SELECT
          sku, product, platform, listing_id, price_usd, listing_status,
          listed_at, views, watchers, offers, watch_rate,
          CASE WHEN listed_at IS NULL THEN NULL
               ELSE EXTRACT(EPOCH FROM (CAST(? AS timestamp) - listed_at)) / 86400.0
          END AS listing_age_days,
          CASE
            WHEN coalesce(watch_rate, 0) >= ? AND coalesce(offers, 0) = 0
              THEN 'high_attention_no_offers'
            WHEN coalesce(views, 0) > 0 AND coalesce(watchers, 0)::numeric / views < 0.04
              THEN 'high_views_low_watchers'
            WHEN coalesce(offers, 0) >= 2 AND listing_status = 'active'
              THEN 'multiple_offers_unsold'
            ELSE 'other'
          END AS performance_flag
        FROM sales.v_listing_performance
        WHERE listing_status = 'active'
        ORDER BY
          CASE
            WHEN coalesce(watch_rate, 0) >= ? AND coalesce(offers, 0) = 0 THEN 0
            ELSE 1
          END,
          coalesce(watch_rate, 0) DESC
        LIMIT ?
        """,
        [_utcnow(), M.HIGH_WATCH_RATE, M.HIGH_WATCH_RATE, limit],
    )
    weak = [r for r in rows if r.get("performance_flag") == "high_attention_no_offers"]
    return BusinessPayload(
        kind="derived",
        data={
            "listings": rows,
            "high_attention_no_offers": weak,
            "threshold_watch_rate": M.HIGH_WATCH_RATE,
        },
        provenance=Provenance(
            tool="get_listing_performance",
            as_of=_utcnow().isoformat(timespec="seconds") + "Z",
            source_relations=["sales.v_listing_performance"],
            metric_names=["watch_rate", "listing_age_days"],
            notes=[
                "DERIVED from listing × engagement rollup.",
                "high_attention_no_offers uses HIGH_WATCH_RATE and zero offers.",
            ],
        ),
    )
