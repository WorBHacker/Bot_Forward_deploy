"""drop legacy zwsp_toggle from analytics_sources

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-12
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE analytics_sources DROP COLUMN IF EXISTS zwsp_toggle"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE analytics_sources ADD COLUMN IF NOT EXISTS zwsp_toggle BOOLEAN NOT NULL DEFAULT false"
    )
