"""Obsidian reseller-item notes → canonical resale records.

The capture UI is one markdown file per sellable SKU with YAML frontmatter.
This adapter validates, slugs identifiers, and records source lineage.
It never embeds a machine-specific filesystem path in public defaults.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ....validate import ItemEventRecord, ItemRecord, ListingEventRecord, ListingRecord

STATUS_MAP = {
    "planned": "planned",
    "owned": "owned",
    "listed": "listed",
    "sold": "sold",
    "in_transit": "in_transit",
    "archived": "archived",
}
GRAILED_LISTING = {"draft", "listed", "sold", "active"}
SKU_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+$")


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def slug_sku(title: str) -> str:
    text = (title or "").lower().replace("—", " ").replace("–", " ")
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if not slug:
        slug = "item"
    if "-" not in slug:
        slug = f"{slug}-item"
    return slug


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    raw = text.lstrip("\ufeff")
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    meta = yaml.safe_load(parts[1]) or {}
    if not isinstance(meta, dict):
        raise TypeError("frontmatter is not a mapping")
    return meta, parts[2]


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").lstrip("$¥€£")
    try:
        return float(text)
    except ValueError:
        return None


def _when(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    text = str(value).strip().replace("Z", "")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def parse_item_note(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "path": path,
        "name": path.name,
        "stem": path.stem,
        "meta": meta,
        "body": body,
        "content_hash": digest,
    }


def note_to_records(
    parsed: dict[str, Any],
    *,
    source_system: str = "obsidian_item_notes",
) -> dict[str, Any]:
    """Return canonical records or a reject reason. Never raises for data issues."""
    meta = dict(parsed.get("meta") or {})
    note_type = meta.get("type")
    if note_type and note_type != "reseller_item":
        return {"reject": f"unsupported type {note_type!r}", "records": None}

    stream = str(meta.get("stream") or "Selling")
    if stream.lower() != "selling":
        return {"reject": f"stream {stream!r} is not Selling", "records": None}

    if "product" in meta:
        product = str(meta.get("product") or "").strip()
    else:
        product = parsed["stem"].split("—")[0].strip()
    if not product:
        return {"reject": "product is required", "records": None}

    sku = slug_sku(parsed["stem"])
    if not SKU_RE.match(sku):
        return {"reject": f"cannot slug sku from {parsed['stem']!r}", "records": None}

    def _str(value: Any) -> str | None:
        if value is None or value == "":
            return None
        return str(value)

    status_raw = str(meta.get("status") or "planned").strip().lower()
    grailed_status = str(meta.get("grailed_status") or "not_listed").strip().lower()
    status = STATUS_MAP.get(status_raw, "owned")
    if grailed_status in {"listed", "active"} and status in {"owned", "planned"}:
        status = "listed"
    if grailed_status == "sold":
        status = "sold"

    source_ref = parsed["name"]
    lineage = {
        "source_system": source_system,
        "source_record_reference": source_ref,
        "content_hash": parsed["content_hash"],
        "observed_at": _now().isoformat(timespec="seconds") + "Z",
        "original_title": parsed["stem"],
        "supplier": meta.get("store"),
        "source_listing_title": meta.get("original_name"),
        "tracking_no_present": bool(meta.get("tracking_no")),
        "grailed_status": grailed_status or None,
    }

    item = {
        "sku": sku,
        "product": product,
        "variant": _str(meta.get("variation")),
        "size": _str(meta.get("size")),
        "category": meta.get("category") or None,
        "condition": "used",
        "acquisition_channel": meta.get("store") or "pinduoduo",
        "acquisition_cost_cny": _num(meta.get("bought_cny")),
        "qty": int(_num(meta.get("qty")) or 1),
        "status": status,
        "target_price_usd": _num(meta.get("grailed_price_usd") or meta.get("target_price_usd")),
        "notes": meta.get("notes") or None,
        "_lineage": lineage,
    }

    events: list[dict[str, Any]] = []
    ordered_at = _when(meta.get("ordered_at")) or _when(meta.get("acquired_at"))
    if status != "planned" or meta.get("ordered") is True:
        events.append(
            {
                "item_sku": sku,
                "event_type": "ordered",
                "event_at": (ordered_at or _now()).isoformat(timespec="seconds"),
                "actor": "item_notes",
                "payload": {
                    "supplier": meta.get("store"),
                    "source_system": source_system,
                    "source_record_reference": source_ref,
                },
            }
        )
    if status in {"owned", "listed", "sold"}:
        received_at = _when(meta.get("received_at")) or ordered_at or _now()
        events.append(
            {
                "item_sku": sku,
                "event_type": "received",
                "event_at": received_at.isoformat(timespec="seconds"),
                "actor": "item_notes",
                "payload": {"source_record_reference": source_ref},
            }
        )

    listings: list[dict[str, Any]] = []
    listing_events: list[dict[str, Any]] = []
    listing_reject = None
    price = _num(meta.get("grailed_price_usd"))
    listed_at = _when(meta.get("listed_at") or meta.get("grailed_listed_at"))
    wants_listing = (
        grailed_status in GRAILED_LISTING
        or bool(meta.get("grailed_url"))
        or price is not None
    )
    if wants_listing and not (price and price > 0 and listed_at):
        listing_reject = "listing requested but price_usd/listed_at missing"
    elif wants_listing and price and price > 0 and listed_at:
        listing_status = {
            "draft": "draft",
            "listed": "active",
            "active": "active",
            "sold": "sold",
            "ended": "ended",
        }.get(grailed_status, "active")
        sold_at = _when(meta.get("sold_at"))
        sold_price = _num(meta.get("sold_price_usd") or meta.get("grailed_sold_usd"))
        if listing_status == "sold" and sold_price is None:
            sold_price = price
        listings.append(
            {
                "item_sku": sku,
                "platform": "grailed",
                "platform_url": meta.get("grailed_url") or None,
                "price_usd": price,
                "status": listing_status,
                "listed_at": listed_at.isoformat(timespec="seconds"),
                "sold_at": None if sold_at is None else sold_at.isoformat(timespec="seconds"),
                "sold_price_usd": sold_price,
                "_lineage": lineage,
            }
        )
        listing_events.append(
            {
                "item_sku": sku,
                "platform": "grailed",
                "event_type": "opened",
                "event_at": listed_at.isoformat(timespec="seconds"),
                "price_usd": price,
                "status": "active" if listing_status != "draft" else "draft",
            }
        )
        events.append(
            {
                "item_sku": sku,
                "event_type": "listed",
                "event_at": listed_at.isoformat(timespec="seconds"),
                "payload": {"price_usd": price, "platform": "grailed"},
            }
        )
        if listing_status == "sold" and sold_at:
            listing_events.append(
                {
                    "item_sku": sku,
                    "platform": "grailed",
                    "event_type": "sold",
                    "event_at": sold_at.isoformat(timespec="seconds"),
                    "price_usd": sold_price,
                    "status": "sold",
                }
            )
            events.append(
                {
                    "item_sku": sku,
                    "event_type": "sold",
                    "event_at": sold_at.isoformat(timespec="seconds"),
                    "payload": {"price_usd": sold_price},
                }
            )

    try:
        ItemRecord.model_validate({k: v for k, v in item.items() if not k.startswith("_")})
        for event in events:
            ItemEventRecord.model_validate(event)
        for listing in listings:
            ListingRecord.model_validate(
                {k: v for k, v in listing.items() if not k.startswith("_")}
            )
        for event in listing_events:
            ListingEventRecord.model_validate(event)
    except ValidationError as exc:
        return {"reject": str(exc), "records": None}

    note_row = None
    body = (parsed.get("body") or "").strip()
    if body:
        note_row = {
            "note_id": f"src-{sku}",
            "kind": "seller_note",
            "title": parsed["stem"],
            "body": body[:4000],
            "object_type": "item",
            "object_id": sku,
        }

    return {
        "reject": None,
        "listing_reject": listing_reject,
        "records": {
            "item": item,
            "events": events,
            "listings": listings,
            "listing_events": listing_events,
            "note": note_row,
        },
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=str) + "\n")
