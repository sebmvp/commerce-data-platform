"""drop DuckDB date_diff compatibility functions

Revision ID: 007_drop_date_diff
Revises: 006_drop_insights
Create Date: 2026-09-13
"""
from __future__ import annotations

from alembic import op

revision = "007_drop_date_diff"
down_revision = "006_drop_insights"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS date_diff(text, timestamp, timestamp)")
    op.execute("DROP FUNCTION IF EXISTS date_diff(text, timestamp, timestamptz)")
    op.execute("DROP FUNCTION IF EXISTS date_diff(text, timestamptz, timestamptz)")
    op.execute("DROP FUNCTION IF EXISTS date_diff(text, timestamptz, timestamp)")


def downgrade() -> None:
    pass
