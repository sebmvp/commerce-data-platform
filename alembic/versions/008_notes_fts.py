"""PostgreSQL full-text search over ops.notes.

Revision ID: 008_notes_fts
Revises: 007_drop_date_diff
"""
from __future__ import annotations

from alembic import op

revision = "008_notes_fts"
down_revision = "007_drop_date_diff"
branch_labels = None
depends_on = None

TSV = (
    "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
    "setweight(to_tsvector('english', coalesce(body, '')), 'B')"
)


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE ops.notes
          ADD COLUMN IF NOT EXISTS search_tsv tsvector
          GENERATED ALWAYS AS ({TSV}) STORED
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS notes_search_tsv ON ops.notes USING GIN (search_tsv)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ops.notes_search_tsv")
    op.execute("ALTER TABLE ops.notes DROP COLUMN IF EXISTS search_tsv")
