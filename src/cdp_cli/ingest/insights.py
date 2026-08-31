"""Insights loaders: published content and its engagement snapshots."""
from __future__ import annotations

import json
from typing import Any

from .base import IngestJob
from ..validate import ContentEngagementRecord, ContentRecord


class ContentIngest(IngestJob[ContentRecord]):
    source = "insights.content_pieces"
    filename = "content_pieces.jsonl"
    model = ContentRecord

    def natural_key(self, rec: ContentRecord) -> str:
        return rec.content_id

    def upsert(self, rec: ContentRecord, raw: dict[str, Any]) -> None:
        self.con.execute(
            """INSERT INTO insights.content_pieces
               (caption_id, item_sku, channel_key, body, tone, cta, hooks,
                status, published_at, raw_json)
               VALUES (?, ?, (SELECT channel_key FROM core.channels
                              WHERE platform=? AND valid_to IS NULL),
                       ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (caption_id) DO UPDATE SET
                 status=excluded.status, tone=excluded.tone, cta=excluded.cta,
                 hooks=excluded.hooks, updated_at=now()""",
            [rec.content_id, rec.item_sku, rec.platform, rec.body, rec.tone,
             rec.cta, rec.hooks, rec.status, rec.published_at,
             json.dumps(raw, default=str)],
        )


class ContentSnapshotIngest(IngestJob[ContentEngagementRecord]):
    source = "insights.content_snapshot"
    filename = "content_snapshots.jsonl"
    model = ContentEngagementRecord

    def natural_key(self, rec: ContentEngagementRecord) -> str:
        return f"{rec.content_id}:{rec.observed_at}:{rec.window_hours}"

    def upsert(self, rec: ContentEngagementRecord, raw: dict[str, Any]) -> None:
        exists = self.con.execute(
            "SELECT 1 FROM insights.content_pieces WHERE caption_id=?",
            [rec.content_id],
        ).fetchone()
        if not exists:
            raise ValueError(f"snapshot references unknown content {rec.content_id}")
        interactions = rec.saves + rec.inquiries
        er = round(interactions / rec.impressions, 6) if rec.impressions else None
        self.con.execute(
            """INSERT INTO insights.content_snapshot
               (snapshot_id, caption_id, observed_at, window_hours, impressions,
                interactions, saves, inquiries, engagement_rate, conversions, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (snapshot_id) DO UPDATE SET
                 impressions=excluded.impressions, saves=excluded.saves,
                 inquiries=excluded.inquiries, conversions=excluded.conversions,
                 engagement_rate=excluded.engagement_rate""",
            [self._id("snap", self.natural_key(rec)), rec.content_id,
             rec.observed_at, rec.window_hours, rec.impressions, interactions,
             rec.saves, rec.inquiries, er, rec.conversions,
             json.dumps(raw, default=str)],
        )
