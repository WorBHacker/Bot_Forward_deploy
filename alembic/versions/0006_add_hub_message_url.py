"""add hub_message_url to analytics_sources

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-12
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE analytics_sources ADD COLUMN IF NOT EXISTS hub_message_url VARCHAR(255)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE analytics_sources DROP COLUMN IF EXISTS hub_message_url"
    )
