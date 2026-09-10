"""Honest source-coverage report for the connected canonical database."""
from __future__ import annotations

from typing import Any

from .db import Connection
from .runtime import world_kind


def source_completeness(con: Connection) -> dict[str, Any]:
    items = con.execute("SELECT count(*) FROM catalog.items").fetchone()[0]
    with_cost = con.execute(
        "SELECT count(*) FROM catalog.items WHERE acquisition_cost_cny IS NOT NULL"
    ).fetchone()[0]
    listings = con.execute("SELECT count(*) FROM sales.listings").fetchone()[0]
    engagement = con.execute(
        "SELECT count(*) FROM sales.engagement_metric"
    ).fetchone()[0]
    orders = con.execute("SELECT count(*) FROM sales.orders").fetchone()[0]
    notes = con.execute("SELECT count(*) FROM ops.notes").fetchone()[0]
    actions = con.execute("SELECT count(*) FROM ops.actions").fetchone()[0]
    kind = world_kind()
    missing: list[str] = []
    if kind == "private":
        if listings == 0:
            missing.append("marketplace listing export")
        if orders == 0:
            missing.append("sold/order export")
        if engagement == 0:
            missing.append("engagement export")
    return {
        "environment": kind,
        "synthetic": kind != "private",
        "counts": {
            "items": int(items or 0),
            "acquisition_cost": int(with_cost or 0),
            "listings": int(listings or 0),
            "engagement_snapshots": int(engagement or 0),
            "orders": int(orders or 0),
            "notes": int(notes or 0),
            "sandbox_actions": int(actions or 0),
        },
        "missing_source_systems": missing,
        "notes": [
            "Counts describe the connected canonical database only.",
            "Private mode reports only what source evidence supported.",
            "Demo/held-out worlds are synthetic.",
        ],
    }
