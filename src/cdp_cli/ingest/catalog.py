"""Catalog loaders: items and their event stream."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .base import IngestJob, _now
from ..validate import ChannelRecord, ItemEventRecord, ItemRecord


class ChannelIngest(IngestJob[ChannelRecord]):
    """Channels with SCD-2 handling: a changed fee/standing closes the
    current version and opens a new one."""

    source = "core.channels"
    filename = "channels.jsonl"
    model = ChannelRecord

    def natural_key(self, rec: ChannelRecord) -> str:
        # Key includes valid_from so each SCD-2 version is a distinct row —
        # a changed fee opens a new version instead of colliding on PK.
        return f"{rec.platform}/{rec.handle}@{rec.valid_from.isoformat()}"

    def upsert(self, rec: ChannelRecord, raw: dict[str, Any]) -> None:
        key = self.natural_key(rec)
        # idempotent: this exact version already ingested?
        exact = self.con.execute(
            """SELECT 1 FROM core.channels
               WHERE channel_key=? AND standing=? AND fee_pct=?""",
            [key, rec.standing, rec.fee_pct],
        ).fetchone()
        if exact:
            return

        current = self.con.execute(
            """SELECT channel_key, standing, fee_pct FROM core.channels
               WHERE platform=? AND handle=? AND valid_to IS NULL""",
            [rec.platform, rec.handle],
        ).fetchone()

        if current:
            if current[1] == rec.standing and abs(current[2] - rec.fee_pct) < 1e-9:
                return  # same values, different window — nothing to do
            self.con.execute(
                "UPDATE core.channels SET valid_to=?, updated_at=? WHERE channel_key=?",
                [_now(), _now(), current[0]],
            )
        self.con.execute(
            """INSERT INTO core.channels
               (channel_key, platform, handle, standing, region, fee_pct,
                valid_from, source_file)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [key, rec.platform, rec.handle, rec.standing, rec.region,
             rec.fee_pct, rec.valid_from, str(self.path)],
        )


class ItemIngest(IngestJob[ItemRecord]):
    source = "catalog.items"
    filename = "catalog_items.jsonl"
    model = ItemRecord

    def natural_key(self, rec: ItemRecord) -> str:
        return rec.sku

    def upsert(self, rec: ItemRecord, raw: dict[str, Any]) -> None:
        item_id = self._id("item", rec.sku)
        self.con.execute(
            """INSERT INTO catalog.items
               (item_id, sku, product, variant, size, category_key, condition,
                acquisition_channel, acquisition_cost_cny, qty, qty_available,
                status, target_price_usd, notes, source_file, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (sku) DO UPDATE SET
                 product=excluded.product, variant=excluded.variant,
                 size=excluded.size, category_key=excluded.category_key,
                 condition=excluded.condition,
                 acquisition_cost_cny=excluded.acquisition_cost_cny,
                 qty=excluded.qty, status=excluded.status,
                 target_price_usd=excluded.target_price_usd,
                 notes=excluded.notes, raw_json=excluded.raw_json,
                 updated_at=now()""",
            [item_id, rec.sku, rec.product, rec.variant, rec.size, rec.category,
             rec.condition, rec.acquisition_channel, rec.acquisition_cost_cny,
             rec.qty, rec.qty if rec.status in ("owned", "planned") else 0,
             rec.status, rec.target_price_usd, rec.notes, str(self.path),
             json.dumps(raw, default=str)],
        )


class ItemEventIngest(IngestJob[ItemEventRecord]):
    source = "catalog.item_events"
    filename = "item_events.jsonl"
    model = ItemEventRecord

    def natural_key(self, rec: ItemEventRecord) -> str:
        return f"{rec.item_sku}:{rec.event_type}:{rec.event_at}"

    def upsert(self, rec: ItemEventRecord, raw: dict[str, Any]) -> None:
        row = self.con.execute(
            "SELECT item_id FROM catalog.items WHERE sku=?", [rec.item_sku]
        ).fetchone()
        if not row:
            raise ValueError(f"event references unknown item sku={rec.item_sku}")
        event_id = self._id("event", self.natural_key(rec))
        self.con.execute(
            """INSERT INTO catalog.item_events
               (event_id, item_id, event_type, event_at, actor, payload_json)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT (event_id) DO NOTHING""",
            [event_id, row[0], rec.event_type,
             rec.event_at or datetime.now(), rec.actor,
             json.dumps(rec.payload or {}, default=str)],
        )
