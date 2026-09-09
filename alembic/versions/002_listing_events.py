"""listing events for as-of reconstruction

Revision ID: 002_listing_events
Revises: 001_canonical
Create Date: 2026-09-09
"""
from __future__ import annotations

from alembic import op

revision = "002_listing_events"
down_revision = "001_canonical"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sales.listing_events (
          event_id    TEXT PRIMARY KEY,
          listing_id  TEXT NOT NULL REFERENCES sales.listings (listing_id),
          event_type  TEXT NOT NULL,
          event_at    TIMESTAMP NOT NULL,
          price_usd   DOUBLE PRECISION,
          status      TEXT,
          payload_json JSONB
        );
        CREATE INDEX IF NOT EXISTS listing_events_listing
          ON sales.listing_events (listing_id, event_at);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sales.listing_events")
