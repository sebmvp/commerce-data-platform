"""drop unused insights schema

Revision ID: 006_drop_insights
Revises: 005_record_lineage
Create Date: 2026-09-13
"""
from __future__ import annotations

from alembic import op

revision = "006_drop_insights"
down_revision = "005_record_lineage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS insights CASCADE")


def downgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS insights")
