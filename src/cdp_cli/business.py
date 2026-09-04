"""Typed business query layer — deterministic answers with provenance.

This is the AI-ready tool surface *without* an LLM. Every function returns
structured facts plus enough metadata for a later copilot to cite evidence.

FACT vs DERIVED vs RECOMMENDATION are labeled explicitly in payloads.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

import duckdb

from . import metrics as M
from .observability import trust_report

Kind = Literal["fact", "derived", "recommendation"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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


def get_business_snapshot(con: duckdb.DuckDBPyConnection) -> BusinessPayload:
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
              AND date_diff('day', listed_at, current_timestamp) >= ?
          ) AS stale_active_listings
        FROM sales.listings
        """,
        [M.STALE_LISTING_DAYS],
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
    con: duckdb.DuckDBPyConnection,
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
            date_diff('day', l.listed_at, current_timestamp) AS listing_age_days,
            coalesce(sum(em.views), 0) AS views,
            coalesce(sum(em.watchers), 0) AS watchers,
            coalesce(sum(em.offers), 0) AS offers,
            CASE WHEN coalesce(sum(em.views), 0) = 0 THEN NULL
                 ELSE round(sum(em.watchers)::DOUBLE / sum(em.views), 4)
            END AS watch_rate
          FROM sales.listings l
          LEFT JOIN core.channels ch
            ON ch.channel_key = l.channel_key AND ch.valid_to IS NULL
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
            date_diff('day', a.acquired_at, current_timestamp) AS inventory_age_days,
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
              WHEN lr.watch_rate IS NOT NULL AND lr.watch_rate >= 0.08
                   AND coalesce(lr.offers, 0) = 0 THEN 'high_attention_no_offers'
              ELSE 'listed_active'
            END AS attention_reason,
            CASE
              WHEN a.status = 'owned' THEN 100
              WHEN lr.listing_age_days >= {M.STALE_LISTING_DAYS} THEN 80
              WHEN lr.watch_rate IS NOT NULL AND lr.watch_rate >= 0.08
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
        [limit],
    ).fetchall()
    cols = [
        "sku", "product", "item_status", "condition",
        "acquisition_cost_cny", "target_price_usd", "inventory_age_days",
        "listing_id", "platform", "listing_price_usd", "listing_age_days",
        "views", "watchers", "offers", "watch_rate",
        "attention_reason", "priority_class",
    ]
    queue = [dict(zip(cols, r)) for r in rows]

    recommendations = []
    for row in queue[:5]:
        reason = row["attention_reason"]
        if reason == "unlisted_owned":
            action = "list_next"
            why = (
                f"{row['sku']} is owned/unlisted with cost basis "
                f"{row['acquisition_cost_cny']} CNY and age "
                f"{row['inventory_age_days']} days — capital is idle."
            )
        elif reason == "stale_listing":
            action = "review_price_or_channel"
            why = (
                f"{row['sku']} active on {row['platform']} for "
                f"{row['listing_age_days']} days "
                f"(threshold {M.STALE_LISTING_DAYS}) without sale."
            )
        elif reason == "high_attention_no_offers":
            action = "consider_reprice"
            why = (
                f"{row['sku']} watch_rate={row['watch_rate']} with 0 offers — "
                f"attention without conversion often means price friction."
            )
        else:
            action = "monitor"
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
            "ranking_notes": [
                "priority_class: unlisted_owned=100, stale_listing=80, "
                "high_attention_no_offers=60, listed_active=20",
                "Within a class: higher capital, then older inventory/listing first",
                "RECOMMENDATION rows are heuristic; FACT rows are the queue metrics",
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
            ],
        ),
    )


def get_ingest_health(con: duckdb.DuckDBPyConnection) -> BusinessPayload:
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
