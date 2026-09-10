"""Sandbox action apply columns.

Revision ID: 003_action_apply
Revises: 002_listing_events
Create Date: 2026-09-10
"""
from __future__ import annotations

from alembic import op

revision = "003_action_apply"
down_revision = "002_listing_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE ops.actions
          ADD COLUMN IF NOT EXISTS applied_at TIMESTAMP,
          ADD COLUMN IF NOT EXISTS context_question TEXT,
          ADD COLUMN IF NOT EXISTS previous_value JSONB,
          ADD COLUMN IF NOT EXISTS resulting_value JSONB;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE ops.actions
          DROP COLUMN IF EXISTS applied_at,
          DROP COLUMN IF EXISTS context_question,
          DROP COLUMN IF EXISTS previous_value,
          DROP COLUMN IF EXISTS resulting_value;
        """
    )
