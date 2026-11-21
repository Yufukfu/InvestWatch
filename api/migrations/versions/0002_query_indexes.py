"""indexes for the dashboard queries (GET /findings filters and sort, /stats/trend) and job_errors lookups

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_findings_detected_at", "findings", [sa.text("detected_at DESC")])
    op.create_index("ix_findings_module", "findings", ["module", sa.text("detected_at DESC")])
    op.create_index("ix_findings_status", "findings", ["status"])
    op.create_index("ix_findings_platform", "findings", ["platform"])
    op.create_index("ix_findings_score", "findings", ["score"])
    op.create_index("ix_job_errors_source_id_occurred_at", "job_errors", ["source_id", sa.text("occurred_at DESC")])


def downgrade() -> None:
    op.drop_index("ix_job_errors_source_id_occurred_at", table_name="job_errors")
    for name in ("ix_findings_score", "ix_findings_platform", "ix_findings_status", "ix_findings_module",
                 "ix_findings_detected_at"):
        op.drop_index(name, table_name="findings")
