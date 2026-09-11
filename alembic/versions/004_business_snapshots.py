"""named business snapshot checkpoints

Revision ID: 004_business_snapshots
Revises: 003_action_apply
Create Date: 2026-09-11
"""
from __future__ import annotations

from alembic import op

revision = "004_business_snapshots"
down_revision = "003_action_apply"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ops.business_snapshots (
          snapshot_id   TEXT PRIMARY KEY,
          captured_at   TIMESTAMP NOT NULL,
          as_of         TIMESTAMP NOT NULL,
          trigger       TEXT NOT NULL,
          payload_json  JSONB NOT NULL,
          content_hash  TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS business_snapshots_captured
          ON ops.business_snapshots (captured_at DESC, as_of DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ops.business_snapshots")
