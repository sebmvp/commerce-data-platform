"""canonical commerce model

Revision ID: 001_canonical
Revises:
Create Date: 2026-09-09
"""
from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "001_canonical"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    root = Path(__file__).resolve().parents[2]
    op.execute((root / "schema" / "001_init.sql").read_text())
    op.execute((root / "sql" / "views.sql").read_text())


def downgrade() -> None:
    for schema in ("ops", "insights", "sales", "supply", "catalog", "core"):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
