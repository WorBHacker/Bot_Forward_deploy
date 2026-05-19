"""add member_count and zwsp_toggle to message_stats

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE message_stats ADD COLUMN IF NOT EXISTS member_count INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE message_stats ADD COLUMN IF NOT EXISTS zwsp_toggle BOOLEAN NOT NULL DEFAULT false")


def downgrade() -> None:
    op.drop_column("message_stats", "zwsp_toggle")
    op.drop_column("message_stats", "member_count")
