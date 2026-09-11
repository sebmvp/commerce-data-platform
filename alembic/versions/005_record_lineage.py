"""record lineage for canonical facts

Revision ID: 005_record_lineage
Revises: 004_business_snapshots
Create Date: 2026-09-11
"""
from __future__ import annotations

from alembic import op

revision = "005_record_lineage"
down_revision = "004_business_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS core.record_lineage (
          lineage_id TEXT PRIMARY KEY,
          entity_type TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          source_system TEXT NOT NULL,
          source_record_reference TEXT,
          content_hash TEXT,
          observed_at TIMESTAMP,
          effective_at TIMESTAMP,
          ingest_run_id TEXT REFERENCES core.ingest_runs (run_id),
          created_at TIMESTAMP DEFAULT (timezone('UTC', now())::timestamp)
        );
        CREATE INDEX IF NOT EXISTS record_lineage_entity
          ON core.record_lineage (entity_type, entity_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS core.record_lineage")
