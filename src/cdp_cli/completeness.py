"""Honest source-coverage report for the connected canonical database."""
from __future__ import annotations

from typing import Any

from .db import Connection
from .runtime import world_kind, world_meta


def _count(con: Connection, sql: str) -> int:
    row = con.execute(sql).fetchone()
    if row is None:
        return 0
    return int(row[0] or 0)


def _coverage_row(label: str, available: bool, *, partial: bool = False, detail: str) -> dict[str, Any]:
    if available and not partial:
        status = "AVAILABLE"
    elif partial:
        status = "PARTIAL"
    else:
        status = "MISSING"
    return {"category": label, "status": status, "detail": detail}


def source_completeness(con: Connection) -> dict[str, Any]:
    items = _count(con, "SELECT count(*) FROM catalog.items")
    with_cost = _count(
        con, "SELECT count(*) FROM catalog.items WHERE acquisition_cost_cny IS NOT NULL"
    )
    listings = _count(con, "SELECT count(*) FROM sales.listings")
    engagement = _count(con, "SELECT count(*) FROM sales.engagement_metric")
    orders = _count(con, "SELECT count(*) FROM sales.orders")
    notes = _count(con, "SELECT count(*) FROM ops.notes")
    actions = _count(con, "SELECT count(*) FROM ops.actions")
    lineage = 0
    try:
        lineage = _count(con, "SELECT count(*) FROM core.record_lineage")
    except Exception:
        lineage = 0
    latest = con.execute(
        """
        SELECT source, status, rows_read, rows_loaded, rows_rejected, finished_at
        FROM core.ingest_runs
        ORDER BY finished_at DESC NULLS LAST
        LIMIT 1
        """
    ).fetchone()
    latest_ingest = None
    if latest:
        latest_ingest = {
            "source": latest[0],
            "status": latest[1],
            "read": latest[2],
            "loaded": latest[3],
            "rejected": latest[4],
            "finished_at": None if latest[5] is None else str(latest[5]),
        }
    kind = world_kind()
    meta = world_meta()
    missing: list[str] = []
    coverage: list[dict[str, Any]]
    if kind == "private":
        coverage = [
            _coverage_row("Item metadata", items > 0, detail="source-supported item notes"),
            _coverage_row(
                "Sourcing state",
                items > 0,
                partial=True,
                detail="store/status/cost when present; timestamps only if observed",
            ),
            _coverage_row(
                "Listing history",
                listings > 0,
                detail="marketplace listing export" if listings else "no listing export loaded",
            ),
            _coverage_row(
                "Orders",
                orders > 0,
                detail="sold/order export" if orders else "no order export loaded",
            ),
            _coverage_row(
                "Engagement",
                engagement > 0,
                detail="engagement export" if engagement else "no engagement export loaded",
            ),
        ]
        if listings == 0:
            missing.append("marketplace listing export")
        if orders == 0:
            missing.append("sold/order export")
        if engagement == 0:
            missing.append("engagement export")
    else:
        coverage = [
            _coverage_row("Item metadata", items > 0, detail="synthetic catalog"),
            _coverage_row("Sourcing state", items > 0, detail="synthetic lifecycle events"),
            _coverage_row("Listing history", listings > 0, detail="synthetic listings + events"),
            _coverage_row("Orders", orders > 0, detail="synthetic orders"),
            _coverage_row("Engagement", engagement > 0, detail="synthetic snapshots"),
        ]
    return {
        "environment": kind,
        "synthetic": kind != "private",
        "world_name": meta.get("name") or kind,
        "world_as_of": meta.get("as_of"),
        "seed": meta.get("seed"),
        "purpose": meta.get("purpose"),
        "counts": {
            "items": items,
            "acquisition_cost": with_cost,
            "listings": listings,
            "engagement_snapshots": engagement,
            "orders": orders,
            "notes": notes,
            "sandbox_actions": actions,
            "lineage_rows": lineage,
        },
        "coverage": coverage,
        "latest_ingest": latest_ingest,
        "missing_source_systems": missing,
        "notes": [
            "Counts describe the connected canonical database only.",
            "Private mode reports only what source evidence supported.",
            "Demo/held-out worlds are synthetic.",
        ],
    }
