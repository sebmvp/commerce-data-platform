"""Listings, channels, and listing performance."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from cdp_cli.db import Connection

from ..metrics import HIGH_WATCH_RATE
from .items import _require_item
from .payload import BusinessPayload, Provenance, _parse_as_of, _records, _utcnow


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
        [_utcnow(), HIGH_WATCH_RATE, HIGH_WATCH_RATE, limit],
    )
    weak = [r for r in rows if r.get("performance_flag") == "high_attention_no_offers"]
    return BusinessPayload(
        kind="derived",
        data={
            "listings": rows,
            "high_attention_no_offers": weak,
            "threshold_watch_rate": HIGH_WATCH_RATE,
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
