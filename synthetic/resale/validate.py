"""Invariants for a generated resale world. Runtime does not import this."""
from __future__ import annotations

from datetime import datetime
from typing import Any


def _parse(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "")
    return datetime.fromisoformat(text)


def validate_world(world: dict[str, list[dict[str, Any]]]) -> list[str]:
    errors: list[str] = []
    items = {row["sku"]: row for row in world.get("items") or []}
    if len(items) != len(world.get("items") or []):
        errors.append("duplicate item sku")
    listings = world.get("listings") or []
    events = world.get("item_events") or []
    listing_events = world.get("listing_events") or []
    orders = world.get("orders") or []
    engagement = world.get("engagement") or []

    for listing in listings:
        sku = listing.get("item_sku")
        if sku not in items:
            errors.append(f"listing references unknown sku {sku}")
            continue
        listed_at = _parse(listing.get("listed_at"))
        sold_at = _parse(listing.get("sold_at"))
        if listed_at is None:
            errors.append(f"{sku} listing missing listed_at")
        if sold_at and listed_at and sold_at < listed_at:
            errors.append(f"{sku} sold_at before listed_at")
        price = listing.get("price_usd")
        if price is None or float(price) < 0:
            errors.append(f"{sku} listing price is negative or missing")
        if listing.get("status") == "sold" and listing.get("sold_price_usd") is None:
            errors.append(f"{sku} sold listing missing sold_price_usd")
        item_status = items[sku].get("status")
        if listing.get("status") == "active" and item_status not in {"listed", "owned"}:
            errors.append(f"{sku} active listing but item status={item_status}")

    for event in events:
        sku = event.get("item_sku")
        if sku not in items:
            errors.append(f"event references unknown sku {sku}")

    listing_keys = {(lst.get("item_sku"), lst.get("platform")) for lst in listings}
    for event in listing_events:
        key = (event.get("item_sku"), event.get("platform"))
        if key not in listing_keys:
            errors.append(f"listing event for unknown listing {key}")

    for order in orders:
        sku = order.get("item_sku")
        if sku not in items:
            errors.append(f"order references unknown sku {sku}")
            continue
        if items[sku].get("status") != "sold":
            errors.append(f"order for {sku} but item is not sold")
        for field in ("price_usd", "fees_usd", "shipping_usd"):
            val = order.get(field)
            if val is not None and float(val) < 0:
                errors.append(f"order {order.get('order_id')} negative {field}")
        price = order.get("price_usd")
        fees = order.get("fees_usd")
        if price is not None and fees is not None and float(fees) > float(price):
            errors.append(f"order {order.get('order_id')} fees exceed price")

    for snap in engagement:
        sku = snap.get("listing_ref")
        platform = snap.get("platform")
        if (sku, platform) not in listing_keys and sku not in items:
            errors.append(f"engagement for unknown listing {sku}@{platform}")
        listed = next(
            (
                lst
                for lst in listings
                if lst.get("item_sku") == sku and lst.get("platform") == platform
            ),
            None,
        )
        if listed:
            listed_at = _parse(listed.get("listed_at"))
            sold_at = _parse(listed.get("sold_at"))
            snap_day = _parse(str(snap.get("snapshot_at")) + "T00:00:00")
            if listed_at and snap_day and snap_day.date() < listed_at.date():
                errors.append(f"engagement for {sku} before listed_at")
            if sold_at and snap_day and snap_day.date() > sold_at.date():
                errors.append(f"engagement for {sku} after sold_at")

    return errors
