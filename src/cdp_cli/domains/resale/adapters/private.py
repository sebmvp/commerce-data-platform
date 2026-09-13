"""Load private resale sources into an isolated PostgreSQL database.

Public demo data is never mixed in. Source directories come from
CDP_PRIVATE_SOURCE / --source, not from hardcoded home paths.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .... import db
from .item_notes import ItemNotesAdapter, note_to_records, parse_item_note, write_jsonl
from .write import persist_resale_batch

PRIVATE_URL_ENV = "CDP_PRIVATE_DATABASE_URL"
SOURCE_ENV = "CDP_PRIVATE_SOURCE"
STAGING_ENV = "CDP_PRIVATE_STAGING"


def private_database_url() -> str:
    return os.environ.get(
        PRIVATE_URL_ENV,
        "postgresql://cdp:cdp@127.0.0.1:5432/cdp_private",
    )


def private_source_dir(explicit: str | Path | None = None) -> Path:
    raw = explicit or os.environ.get(SOURCE_ENV)
    if not raw:
        raise ValueError(
            "private source directory is required "
            f"(set {SOURCE_ENV} or pass --source). "
            "Do not hardcode a personal path."
        )
    path = Path(raw).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"private source directory not found: {path}")
    return path


def staging_dir() -> Path:
    raw = os.environ.get(STAGING_ENV)
    if raw:
        return Path(raw)
    return db.project_root() / "data" / "private"


def _row(record: dict[str, Any]) -> dict[str, Any]:
    lineage = record.pop("_lineage", None) or {}
    out = dict(record)
    out.update(lineage)
    return out


def materialize_item_notes(source: Path, dest: Path) -> dict[str, Any]:
    dest.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    listings: list[dict[str, Any]] = []
    listing_events: list[dict[str, Any]] = []
    notes: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    paths = sorted(p for p in source.glob("*.md") if not p.name.startswith("_"))
    for path in paths:
        parsed = parse_item_note(path)
        result = note_to_records(parsed)
        if result.get("reject") or not result.get("records"):
            rejected.append(
                {
                    "source_record_reference": path.name,
                    "reason": result.get("reject") or "no records",
                }
            )
            continue
        recs = result["records"]
        items.append(_row(recs["item"]))
        events.extend(recs["events"])
        listings.extend(_row(lst) for lst in recs["listings"])
        listing_events.extend(recs["listing_events"])
        if recs.get("note"):
            notes.append(recs["note"])
        if result.get("listing_reject"):
            rejected.append(
                {
                    "source_record_reference": path.name,
                    "reason": result["listing_reject"],
                    "kept": "item",
                }
            )

    channels = []
    # Do not invent a marketplace channel (fees, handle) for private evidence.

    write_jsonl(dest / "catalog_items.jsonl", items)
    write_jsonl(dest / "item_events.jsonl", events)
    write_jsonl(dest / "listings.jsonl", listings)
    write_jsonl(dest / "listing_events.jsonl", listing_events)
    write_jsonl(dest / "notes.jsonl", notes)
    write_jsonl(dest / "channels.jsonl", channels)
    for empty in (
        "engagement_metrics.jsonl",
        "orders.jsonl",
    ):
        write_jsonl(dest / empty, [])
    (dest / "rejects.json").write_text(json.dumps(rejected, indent=2) + "\n")
    (dest / "world.json").write_text(
        json.dumps(
            {
                "name": "private",
                "purpose": "private canonical state from local source evidence",
            },
            indent=2,
        )
        + "\n"
    )
    return {
        "notes_read": len(paths),
        "items": len(items),
        "listings": len(listings),
        "events": len(events),
        "rejected": len(rejected),
        "staging": str(dest),
    }


def ingest_private(
    *,
    source: str | Path | None = None,
    database_url: str | None = None,
    force: bool = True,
) -> dict[str, Any]:
    src = private_source_dir(source)
    url = database_url or private_database_url()
    staging = staging_dir()
    summary = materialize_item_notes(src, staging)
    db.ensure_database(url)
    previous = os.environ.get("CDP_DATABASE_URL")
    previous_data = os.environ.get("CDP_DATA")
    os.environ["CDP_DATABASE_URL"] = url
    os.environ["CDP_DATA"] = str(staging)
    try:
        con = db.connect()
        try:
            if force:
                db.reset_schema(con)
            else:
                db.init_schema(con)
            batch = ItemNotesAdapter(src).adapt()
            persist_resale_batch(con, batch, force=force)
        finally:
            con.close()
    finally:
        if previous is None:
            os.environ.pop("CDP_DATABASE_URL", None)
        else:
            os.environ["CDP_DATABASE_URL"] = previous
        if previous_data is None:
            os.environ.pop("CDP_DATA", None)
        else:
            os.environ["CDP_DATA"] = previous_data
    summary["database"] = url
    return summary
