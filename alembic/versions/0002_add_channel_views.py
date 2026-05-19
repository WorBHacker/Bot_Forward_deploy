"""add channel view tracking to broadcast_messages

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE broadcast_messages ADD COLUMN IF NOT EXISTS channel_views INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE broadcast_messages ADD COLUMN IF NOT EXISTS views_synced_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE broadcast_messages ADD COLUMN IF NOT EXISTS content_full TEXT")
    op.execute("ALTER TABLE broadcast_messages ADD COLUMN IF NOT EXISTS zwsp_toggle BOOLEAN NOT NULL DEFAULT false")


def downgrade() -> None:
    op.drop_column("broadcast_messages", "zwsp_toggle")
    op.drop_column("broadcast_messages", "content_full")
    op.drop_column("broadcast_messages", "views_synced_at")
    op.drop_column("broadcast_messages", "channel_views")
