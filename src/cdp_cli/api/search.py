"""Deterministic operator search over canonical tables.

Business Search is navigational, not the Librarian: it finds known objects
(items, listings, orders, notes) so the operator can open one and act on it.
Plain deterministic SQL only — no context assembly, no ranking model.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .. import db
from ..domains.resale.services import search_notes


def search_business(query: str, limit: int = 20) -> dict[str, Any]:
    """Grouped, human-labeled results. Never raises on empty query."""
    q = (query or "").strip()
    groups: list[dict[str, Any]] = []
    if len(q) < 2:
        for kind in ("Item", "Listing", "Order", "Note"):
            groups.append({"type": kind, "hits": []})
        return {"query": q, "groups": groups}

    length = max(1, min(limit, 50))
    needle = f"%{q.lower()}%"
    con = db.connect(read_only=True)
    try:
        now = _now(con)
        return {
            "query": q,
            "groups": [
                {"type": "Item", "hits": _items(con, needle, length, now)},
                {"type": "Listing", "hits": _listings(con, needle, length)},
                {"type": "Order", "hits": _orders(con, needle, length, now)},
                {"type": "Note", "hits": _notes(con, q, length)},
            ],
        }
    finally:
        con.close()


def _items(con, needle: str, limit: int, now: datetime | None) -> list[dict[str, Any]]:
    rows = _rows(
        con,
        """
        SELECT i.sku, i.product, i.variant, i.size, i.status,
               i.acquisition_cost_cny
        FROM catalog.items i
        WHERE lower(coalesce(i.product, '')) LIKE ?
           OR lower(coalesce(i.sku, '')) LIKE ?
           OR lower(coalesce(i.variant, '')) LIKE ?
        ORDER BY length(i.sku), i.sku
        LIMIT ?
        """,
        [needle, needle, needle, limit],
    )
    hits: list[dict[str, Any]] = []
    for r in rows:
        bits = [r.get("status") or "", r.get("size") or ""]
        hits.append(
            {
                "id": r["sku"],
                "sku": r["sku"],
                "kind": "Item",
                "label": _label(r),
                "state": r.get("status"),
                "meta": " · ".join(b for b in bits if b),
                "href": f"/inventory/{r['sku']}",
            }
        )
    return hits


def _listings(con, needle: str, limit: int) -> list[dict[str, Any]]:
    rows = _rows(
        con,
        """
        SELECT l.listing_id, l.platform_url, l.status, l.price_usd,
               i.sku, i.product, i.size
        FROM sales.listings l
        JOIN catalog.items i ON i.item_id = l.item_id
        WHERE lower(coalesce(i.product, '')) LIKE ?
           OR lower(coalesce(l.listing_id, '')) LIKE ?
           OR lower(coalesce(l.status, '')) LIKE ?
        ORDER BY l.listing_id
        LIMIT ?
        """,
        [needle, needle, needle, limit],
    )
    return [
        {
            "id": r["listing_id"],
            "sku": r["sku"],
            "kind": "Listing",
            "label": f"{r['product']}{(' · ' + r['size']) if r.get('size') else ''}",
            "state": r.get("status"),
            "meta": _listing_meta(r),
            "href": f"/inventory/{r['sku']}",
        }
        for r in rows
    ]


def _listing_meta(r: dict[str, Any]) -> str:
    url = r.get("platform_url") or ""
    if "//" in url:
        platform = url.split("//", 1)[1].split("/")[0].replace("www.", "")
        platform = platform.split(".")[0].capitalize()  # grailed.example → Grailed
    elif "/" in url:
        platform = url.split("/")[0]
    else:
        platform = "listing"
    price = f"${r['price_usd']:.0f}" if r.get("price_usd") is not None else ""
    return " · ".join(str(p) for p in (platform, price) if p)


def _channel(value: Any) -> str:
    raw = str(value or "")
    name = raw.split("/")[0].split("@")[0] if raw else ""
    return name.capitalize() if name else "Channel"


def _orders(con, needle: str, limit: int, now: datetime | None) -> list[dict[str, Any]]:
    rows = _rows(
        con,
        """
        SELECT o.order_id, o.channel_key, o.status, o.price_usd,
               o.order_at, i.sku, i.product
        FROM sales.orders o
        JOIN catalog.items i ON i.item_id = o.item_id
        WHERE lower(coalesce(i.product, '')) LIKE ?
           OR lower(coalesce(o.order_id, '')) LIKE ?
           OR lower(coalesce(o.channel_key, '')) LIKE ?
        ORDER BY o.order_at DESC NULLS LAST, o.order_id
        LIMIT ?
        """,
        [needle, needle, needle, limit],
    )
    hits: list[dict[str, Any]] = []
    for r in rows:
        days = _days(r.get("order_at"), now)
        parts = [_channel(r.get("channel_key")), r.get("status") or ""]
        if r.get("price_usd") is not None:
            parts.append(f"${r['price_usd']:.0f}")
        if days:
            parts.append(f"{days}d ago")
        hits.append(
            {
                "id": r["order_id"],
                "sku": r["sku"],
                "kind": "Order",
                "label": r["product"],
                "state": r.get("status"),
                "meta": " · ".join(p for p in parts if p),
                "href": f"/inventory/{r['sku']}",
            }
        )
    return hits


def _notes(con, q: str, limit: int) -> list[dict[str, Any]]:
    try:
        found = search_notes(con, query=q, limit=limit)
    except Exception:
        return []
    hits: list[dict[str, Any]] = []
    for n in found[:limit]:
        ref = str(n.get("object_id") or "")
        item_id = ref.split(":")[-1] if ":" in ref else ref
        text = str(n.get("body") or n.get("title") or "")
        snippet = text[:120]
        hits.append(
            {
                "id": str(n.get("note_id") or n.get("title") or ""),
                "sku": item_id,
                "kind": "Note",
                "label": str(n.get("title") or snippet),
                "state": str(n.get("kind") or ""),
                "meta": f"on {item_id}" if item_id else "",
                "href": f"/inventory/{item_id}" if item_id else None,
            }
        )
    return hits


def _label(row: dict[str, Any]) -> str:
    base = str(row.get("product") or row.get("sku") or "")
    size = row.get("size")
    variant = row.get("variant")
    bits = [str(b) for b in (variant, size) if b]
    return f"{base}{' · ' if bits else ''}{' · '.join(bits)}"


def _now(con) -> datetime | None:
    """World as-of (latest item creation) as the reference clock."""
    try:
        rel = con.execute("SELECT max(created_at) FROM catalog.items")
        row = rel.fetchone()
        value = row[0] if row and row[0] else None
        if isinstance(value, datetime):
            return value
        if value:
            return datetime.fromisoformat(str(value).replace(" ", "T"))
    except Exception:
        return None
    return None


def _days(value: Any, now: datetime | None) -> str | None:
    if value is None or now is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace(" ", "T"))
        except ValueError:
            return None
    if dt.tzinfo != now.tzinfo:
        if dt.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=dt.tzinfo)
        elif dt.tzinfo is None and now.tzinfo is not None:
            dt = dt.replace(tzinfo=now.tzinfo)
    return str(max(0, (now - dt).days))


def _rows(con, sql: str, params: list[Any]) -> list[dict[str, Any]]:
    rel = con.execute(sql, params)
    cols = [c[0] for c in rel.description]
    return [dict(zip(cols, r)) for r in rel.fetchall()]
