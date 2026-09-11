"""Shared resale lifecycle primitives for synthetic worlds.

Runtime src/ must not import this package.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat(timespec="seconds")


def item_row(**kw: Any) -> dict[str, Any]:
    base = {
        "variant": None,
        "size": None,
        "category": "catalog.sneakers",
        "condition": "used",
        "acquisition_channel": "wholesale",
        "qty": 1,
        "notes": "synthetic public fixture",
        "target_price_usd": None,
        "acquisition_cost_cny": None,
    }
    base.update(kw)
    return base


def events_for(
    sku: str,
    ordered: datetime,
    received: datetime | None,
    listed: datetime | None,
    sold: datetime | None,
    price: float | None = None,
) -> list[dict[str, Any]]:
    out = [
        {
            "item_sku": sku,
            "event_type": "ordered",
            "event_at": iso(ordered),
            "actor": "batchimport",
            "payload": {},
        }
    ]
    if received:
        out.append(
            {
                "item_sku": sku,
                "event_type": "received",
                "event_at": iso(received),
                "actor": "batchimport",
                "payload": {},
            }
        )
    if listed:
        out.append(
            {
                "item_sku": sku,
                "event_type": "listed",
                "event_at": iso(listed),
                "payload": {"price_usd": price},
            }
        )
    if sold:
        out.append(
            {
                "item_sku": sku,
                "event_type": "sold",
                "event_at": iso(sold),
                "payload": {},
            }
        )
    return out


def engagement_series(
    sku: str,
    platform: str,
    start: datetime,
    days: int,
    *,
    views_base: int,
    watch_frac: float,
    offer_frac: float,
    rng: Any,
) -> list[dict[str, Any]]:
    rows = []
    for d in range(1, days + 1):
        day_gain = max(2, int(views_base * (0.9**d) * rng.uniform(0.7, 1.2)))
        watchers = max(0, int(day_gain * watch_frac))
        offers = max(0, int(day_gain * offer_frac))
        offers = min(offers, watchers)
        rows.append(
            {
                "listing_ref": sku,
                "platform": platform,
                "snapshot_at": (start + timedelta(days=d)).date().isoformat(),
                "views": day_gain,
                "watchers": watchers,
                "offers": offers,
            }
        )
    return rows
