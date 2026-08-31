"""Sales loaders: listings, daily engagement snapshots, orders."""
from __future__ import annotations

import json
from typing import Any

from .base import IngestJob
from ..validate import EngagementRecord, ListingRecord, OrderRecord


class ListingIngest(IngestJob[ListingRecord]):
    source = "sales.listings"
    filename = "listings.jsonl"
    model = ListingRecord

    def natural_key(self, rec: ListingRecord) -> str:
        return f"{rec.item_sku}:{rec.platform}"

    def upsert(self, rec: ListingRecord, raw: dict[str, Any]) -> None:
        item = self.con.execute(
            "SELECT item_id, size FROM catalog.items WHERE sku=?", [rec.item_sku]
        ).fetchone()
        if not item:
            raise ValueError(f"listing references unknown item sku={rec.item_sku}")
        channel = self.con.execute(
            """SELECT channel_key FROM core.channels
               WHERE platform=? AND valid_to IS NULL""",
            [rec.platform],
        ).fetchone()
        listing_id = self._id("listing", self.natural_key(rec))
        self.con.execute(
            """INSERT INTO sales.listings
               (listing_id, item_id, channel_key, platform_url, price_usd,
                status, listed_at, sold_at, sold_price_usd, source_file, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (listing_id) DO UPDATE SET
                 status=excluded.status, sold_at=excluded.sold_at,
                 sold_price_usd=excluded.sold_price_usd,
                 price_usd=excluded.price_usd,
                 updated_at=now()""",
            [listing_id, item[0], channel[0] if channel else None,
             rec.platform_url, rec.price_usd, rec.status, rec.listed_at,
             rec.sold_at, rec.sold_price_usd, str(self.path),
             json.dumps(raw, default=str)],
        )


class EngagementIngest(IngestJob[EngagementRecord]):
    source = "sales.engagement_metric"
    filename = "engagement_metrics.jsonl"
    model = EngagementRecord

    def natural_key(self, rec: EngagementRecord) -> str:
        return f"{rec.listing_ref}:{rec.snapshot_at}"

    def upsert(self, rec: EngagementRecord, raw: dict[str, Any]) -> None:
        listing = self.con.execute(
            """SELECT l.listing_id FROM sales.listings l
               JOIN catalog.items i ON i.item_id = l.item_id
               JOIN core.channels ch ON ch.channel_key = l.channel_key
                                  AND ch.platform = ?
               WHERE i.sku = ?""",
            [rec.platform, rec.listing_ref],
        ).fetchone()
        if not listing:
            listing = self.con.execute(
                "SELECT listing_id FROM sales.listings WHERE listing_id=?",
                [rec.listing_ref],
            ).fetchone()
        if not listing:
            raise ValueError(
                f"engagement references unknown listing {rec.listing_ref}@{rec.platform}")
        metric_id = self._id("eng", listing[0], rec.snapshot_at)
        self.con.execute(
            """INSERT INTO sales.engagement_metric
               (metric_id, listing_id, snapshot_at, views, watchers, offers, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (listing_id, snapshot_at) DO UPDATE SET
                 views=excluded.views, watchers=excluded.watchers,
                 offers=excluded.offers""",
            [metric_id, listing[0], rec.snapshot_at, rec.views, rec.watchers,
             rec.offers, json.dumps(raw, default=str)],
        )


class OrderIngest(IngestJob[OrderRecord]):
    source = "sales.orders"
    filename = "orders.jsonl"
    model = OrderRecord

    def natural_key(self, rec: OrderRecord) -> str:
        return rec.order_id

    def upsert(self, rec: OrderRecord, raw: dict[str, Any]) -> None:
        item = self.con.execute(
            "SELECT item_id FROM catalog.items WHERE sku=?", [rec.item_sku]
        ).fetchone()
        if not item:
            raise ValueError(f"order references unknown item sku={rec.item_sku}")
        channel = self.con.execute(
            "SELECT channel_key FROM core.channels WHERE platform=? AND valid_to IS NULL",
            [rec.platform],
        ).fetchone()
        listing = self.con.execute(
            "SELECT listing_id FROM sales.listings WHERE item_id=? AND status='sold'",
            [item[0]],
        ).fetchone()
        self.con.execute(
            """INSERT INTO sales.orders
               (order_line_key, order_id, line_no, channel_key, item_id, listing_id,
                qty, price_usd, revenue_usd, fees_usd, shipping_usd, status,
                order_at, payload_json, source_file)
               VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (order_line_key) DO UPDATE SET
                 status=excluded.status, updated_at=now()""",
            [rec.order_id, rec.order_id, channel[0] if channel else None,
             item[0], listing[0] if listing else None, rec.qty, rec.price_usd,
             round(rec.qty * rec.price_usd, 2), rec.fees_usd, rec.shipping_usd,
             rec.status, rec.order_at, json.dumps(raw, default=str),
             str(self.path)],
        )
