"""Persist adapted resale records through shared ingest + domain upserts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from cdp_cli.db import Connection
from cdp_cli.ingest.catalog import ChannelIngest, ItemEventIngest, ItemIngest
from cdp_cli.ingest.contract import AdaptedRecord
from cdp_cli.ingest.notes import NoteIngest
from cdp_cli.ingest.runner import persist_adapted_batch
from cdp_cli.ingest.sales import ListingEventIngest, ListingIngest
from cdp_cli.validate import (
    ItemEventRecord,
    ItemRecord,
    ListingEventRecord,
    ListingRecord,
    NoteRecord,
)


def persist_resale_batch(con: Connection, batch, *, force: bool = True) -> dict[str, Any]:
    dummy = Path(".")
    jobs = {
        "item": ItemIngest(con, dummy),
        "item_event": ItemEventIngest(con, dummy),
        "listing": ListingIngest(con, dummy),
        "listing_event": ListingEventIngest(con, dummy),
        "note": NoteIngest(con, dummy),
        "channel": ChannelIngest(con, dummy),
    }
    models = {
        "item": ItemRecord,
        "item_event": ItemEventRecord,
        "listing": ListingRecord,
        "listing_event": ListingEventRecord,
        "note": NoteRecord,
    }

    def upsert(rec: AdaptedRecord) -> None:
        job = jobs.get(rec.entity_type)
        model_cls = models.get(rec.entity_type)
        if job is None or model_cls is None:
            raise ValueError(f"unsupported entity_type {rec.entity_type}")
        payload = {k: v for k, v in rec.payload.items() if not str(k).startswith("_")}
        model = model_cls.model_validate(payload)
        job.path = Path(f"adapter://{rec.lineage.source_system}/{rec.lineage.source_record_reference}")
        raw = dict(payload)
        raw.update(rec.lineage.to_dict())
        job.upsert(model, raw)

    order = ["item", "item_event", "listing", "listing_event", "note", "channel"]
    batch.records.sort(key=lambda r: order.index(r.entity_type) if r.entity_type in order else 99)
    return persist_adapted_batch(
        con,
        batch,
        upsert=upsert,
        source=batch.source_system,
        force=force,
        file_path=f"adapter://{batch.source_system}",
    )
