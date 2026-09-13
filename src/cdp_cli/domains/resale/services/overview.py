"""Operation snapshot and ingest-health tools."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from typing import Any

from cdp_cli.db import Connection
from cdp_cli.observability import trust_report

from ..metrics import CNY_TO_USD_EST, STALE_LISTING_DAYS, get_metric
from .payload import (
    BusinessPayload,
    Provenance,
    _parse_as_of,
    _records,
    _utcnow,
)

SNAPSHOT_DIFF_KEYS = (
    "owned_unlisted",
    "listed_items",
    "sold_items",
    "capital_items",
    "capital_tied_up_cny",
    "items_total",
    "active_listings",
    "stale_active_listings",
    "orders",
    "realized_revenue_usd",
    "realized_gross_after_fees_usd",
)


def _snapshot_payload(
    *,
    as_of: datetime,
    items: tuple[Any, ...],
    listings: tuple[Any, ...],
    orders: tuple[Any, ...],
    trust,
    covered: bool,
    reconstructed: bool,
) -> dict[str, Any]:
    return {
        "as_of": as_of.isoformat(timespec="seconds"),
        "covered": covered,
        "reconstructed": reconstructed,
        "owned_unlisted": int(items[0] or 0),
        "listed_items": int(items[1] or 0),
        "sold_items": int(items[2] or 0),
        "capital_items": int(items[3] or 0),
        "capital_tied_up_cny": float(items[4] or 0),
        "capital_tied_up_usd_est": round(float(items[4] or 0) * CNY_TO_USD_EST, 2),
        "items_total": int(items[5] or 0),
        "active_listings": int(listings[0] or 0),
        "stale_active_listings": int(listings[1] or 0),
        "stale_listing_days_threshold": STALE_LISTING_DAYS,
        "orders": int(orders[0] or 0),
        "realized_revenue_usd": float(orders[1] or 0),
        "realized_gross_after_fees_usd": float(orders[2] or 0),
        "warehouse_trust_ok": trust.ok,
        "warehouse_trust_reasons": list(trust.reasons),
        "fx_note": f"USD estimate uses CNY_TO_USD_EST={CNY_TO_USD_EST} display rate only",
    }


def _snapshot_current(con: Connection, at: datetime) -> dict[str, Any]:
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
              AND (CAST(? AS date) - listed_at::date) >= ?
          ) AS stale_active_listings
        FROM sales.listings
        """,
        [at, STALE_LISTING_DAYS],
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
    return _snapshot_payload(
        as_of=at,
        items=items,
        listings=listings,
        orders=orders,
        trust=trust_report(con),
        covered=True,
        reconstructed=False,
    )


def _snapshot_as_of(con: Connection, at: datetime) -> dict[str, Any]:
    """Rebuild counts from listing dates + item_events at as_of.

    catalog.items.status is the live projection. Asking what the operation
    looked like last week has to walk history or it silently reports today.
    """
    coverage = con.execute(
        """
        SELECT
          (SELECT count(*) FROM catalog.item_events WHERE event_at <= ?) AS events,
          (SELECT count(*) FROM sales.listings
            WHERE listed_at IS NOT NULL AND listed_at <= ?) AS listings
        """,
        [at, at],
    ).fetchone()
    covered = int(coverage[0] or 0) > 0 or int(coverage[1] or 0) > 0
    if not covered:
        empty = (0, 0, 0, 0, 0, 0)
        return _snapshot_payload(
            as_of=at,
            items=empty,
            listings=(0, 0),
            orders=(0, 0, 0),
            trust=trust_report(con),
            covered=False,
            reconstructed=True,
        )
    items = con.execute(
        """
        WITH last_event AS (
          SELECT item_id, event_type,
            row_number() OVER (
              PARTITION BY item_id ORDER BY event_at DESC, event_id DESC
            ) AS rn
          FROM catalog.item_events
          WHERE event_at <= ?
        ),
        listing_state AS (
          SELECT item_id,
            bool_or(sold_at IS NOT NULL AND sold_at <= ?) AS sold,
            bool_or(
              listed_at IS NOT NULL AND listed_at <= ?
              AND (sold_at IS NULL OR sold_at > ?)
            ) AS listed
          FROM sales.listings
          GROUP BY item_id
        ),
        existed AS (
          SELECT i.item_id, i.acquisition_cost_cny,
            CASE
              WHEN coalesce(ls.listed, false) THEN 'listed'
              WHEN coalesce(ls.sold, false) THEN 'sold'
              WHEN le.event_type IN ('sold') THEN 'sold'
              WHEN le.event_type IN ('listed', 'price_change') THEN 'listed'
              WHEN le.event_type IN ('received', 'delisted') THEN 'owned'
              WHEN le.event_type = 'ordered' THEN 'planned'
              ELSE 'owned'
            END AS status_at
          FROM catalog.items i
          LEFT JOIN last_event le ON le.item_id = i.item_id AND le.rn = 1
          LEFT JOIN listing_state ls ON ls.item_id = i.item_id
          WHERE le.item_id IS NOT NULL OR ls.item_id IS NOT NULL
        )
        SELECT
          count(*) FILTER (WHERE status_at = 'owned') AS owned_unlisted,
          count(*) FILTER (WHERE status_at = 'listed') AS listed_items,
          count(*) FILTER (WHERE status_at = 'sold') AS sold_items,
          count(*) FILTER (WHERE status_at IN ('owned','listed')) AS capital_items,
          coalesce(sum(acquisition_cost_cny)
                   FILTER (WHERE status_at IN ('owned','listed')), 0) AS capital_tied_up_cny,
          count(*) AS items_total
        FROM existed
        """,
        [at, at, at, at],
    ).fetchone()
    listings = con.execute(
        """
        SELECT
          count(*) FILTER (
            WHERE listed_at IS NOT NULL AND listed_at <= ?
              AND (sold_at IS NULL OR sold_at > ?)
          ) AS active_listings,
          count(*) FILTER (
            WHERE listed_at IS NOT NULL AND listed_at <= ?
              AND (sold_at IS NULL OR sold_at > ?)
              AND (CAST(? AS date) - listed_at::date) >= ?
          ) AS stale_active_listings
        FROM sales.listings
        """,
        [at, at, at, at, at, STALE_LISTING_DAYS],
    ).fetchone()
    orders = con.execute(
        """
        SELECT
          count(*) FILTER (
            WHERE status != 'cancelled' AND order_at IS NOT NULL AND order_at <= ?
          ) AS orders,
          coalesce(sum(revenue_usd) FILTER (
            WHERE status != 'cancelled' AND order_at IS NOT NULL AND order_at <= ?
          ), 0) AS realized_revenue_usd,
          coalesce(sum(revenue_usd - coalesce(fees_usd,0) - coalesce(shipping_usd,0))
                   FILTER (
                     WHERE status != 'cancelled'
                       AND order_at IS NOT NULL AND order_at <= ?
                   ), 0) AS realized_gross_after_fees_usd
        FROM sales.orders
        """,
        [at, at, at],
    ).fetchone()
    return _snapshot_payload(
        as_of=at,
        items=items,
        listings=listings,
        orders=orders,
        trust=trust_report(con),
        covered=True,
        reconstructed=True,
    )


def get_business_snapshot(
    con: Connection,
    as_of: datetime | date | str | None = None,
) -> BusinessPayload:
    """Resale operation counts + capital, not a recommendation.

    Omit as_of for the live projection. Pass as_of to reconstruct from
    listing dates and item_events — that is how recent_changes gets a
    previous checkpoint without inventing one.
    """
    at = _parse_as_of(as_of)
    reconstructed = as_of is not None
    data = _snapshot_as_of(con, at) if reconstructed else _snapshot_current(con, at)
    notes = [
        "DERIVED: capital sums, stale counts, fee-adjusted gross.",
        "realized_gross_after_fees_usd is NOT full margin (excludes acquisition cost).",
    ]
    if reconstructed:
        notes.insert(
            0,
            "FACT: reconstructed from listing listed_at/sold_at and item_events at as_of.",
        )
        relations = [
            "catalog.item_events",
            "sales.listings",
            "sales.orders",
            "catalog.items",
        ]
    else:
        notes.insert(0, "FACT: row counts from current projections.")
        relations = [
            "catalog.items",
            "sales.listings",
            "sales.orders",
            "core.ingest_runs",
        ]
    return BusinessPayload(
        kind="derived",
        data=data,
        provenance=Provenance(
            tool="get_business_snapshot",
            as_of=at.isoformat(timespec="seconds") + "Z",
            source_relations=relations,
            metric_names=[
                "capital_tied_up_cny",
                "unlisted_owned_count",
                "stale_listing",
                "realized_revenue_usd",
                "realized_gross_after_fees_usd",
            ],
            notes=notes,
        ),
    )


def diff_snapshots(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Numeric deltas between two snapshot payloads. Unchanged keys omitted."""
    out: dict[str, Any] = {}
    for key in SNAPSHOT_DIFF_KEYS:
        before = previous.get(key)
        after = current.get(key)
        if before == after:
            continue
        try:
            delta = float(after) - float(before)
        except (TypeError, ValueError):
            delta = None
        out[key] = {"from": before, "to": after, "delta": delta}
    return out


def capture_business_snapshot(
    con: Connection,
    *,
    trigger: str,
    as_of: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Persist a named checkpoint. Does not replace event history."""
    trigger = (trigger or "manual").strip() or "manual"
    payload = get_business_snapshot(con, as_of=as_of)
    data = dict(payload.data)
    at = _parse_as_of(as_of)
    blob = json.dumps(data, sort_keys=True, default=str)
    content_hash = hashlib.sha256(blob.encode()).hexdigest()[:16]
    snapshot_id = hashlib.sha256(
        f"{trigger}:{at.isoformat(timespec='seconds')}:{content_hash}".encode()
    ).hexdigest()[:16]
    captured = _utcnow()
    con.execute(
        """
        INSERT INTO ops.business_snapshots
          (snapshot_id, captured_at, as_of, trigger, payload_json, content_hash)
        VALUES (?, ?, ?, ?, ?::jsonb, ?)
        ON CONFLICT (snapshot_id) DO NOTHING
        """,
        [
            snapshot_id,
            captured,
            at,
            trigger,
            blob,
            content_hash,
        ],
    )
    return {
        "snapshot_id": snapshot_id,
        "captured_at": captured.isoformat(timespec="seconds") + "Z",
        "as_of": at.isoformat(timespec="seconds") + "Z",
        "trigger": trigger,
        "content_hash": content_hash,
        "payload": data,
    }


def list_business_snapshots(con: Connection, *, limit: int = 20) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 100))
    rows = _records(
        con,
        """
        SELECT snapshot_id, captured_at, as_of, trigger, payload_json, content_hash
        FROM ops.business_snapshots
        ORDER BY captured_at DESC, as_of DESC
        LIMIT ?
        """,
        [limit],
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        payload = row.get("payload_json")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
        out.append(
            {
                "snapshot_id": row["snapshot_id"],
                "captured_at": row["captured_at"],
                "as_of": row["as_of"],
                "trigger": row["trigger"],
                "content_hash": row["content_hash"],
                "payload": payload or {},
            }
        )
    return out


def ensure_baseline_snapshots(con: Connection) -> list[dict[str, Any]]:
    """After ingest, persist prior-window + current so the demo has checkpoints."""
    now = _utcnow()
    prior = capture_business_snapshot(
        con,
        trigger="as_of_reconstruction",
        as_of=now - timedelta(days=STALE_LISTING_DAYS),
    )
    current = capture_business_snapshot(con, trigger="post_ingest")
    return [prior, current]

def get_ingest_health(con: Connection) -> BusinessPayload:
    report = trust_report(con)
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
    m = get_metric(name)
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
            source_relations=["cdp_cli.domains.resale.metrics.METRICS"],
            metric_names=[m.name],
            notes=["Canonical definition registry — not inferred from SQL ad hoc."],
        ),
    )
