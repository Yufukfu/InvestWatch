"""documents.text must not be empty (second line of defence; the scraper never stores empty text)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-21
"""

from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The metadata naming convention (env.py) prefixes the short name: ck_documents_text_not_empty.
    op.create_check_constraint("text_not_empty", "documents", "text <> ''")


def downgrade() -> None:
    op.drop_constraint("text_not_empty", "documents", type_="check")
