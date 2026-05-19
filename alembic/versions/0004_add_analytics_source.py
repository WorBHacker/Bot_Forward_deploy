"""add analytics_sources table for hub-channel view tracking

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS analytics_sources (
            id SERIAL PRIMARY KEY,
            broadcast_id INTEGER NOT NULL REFERENCES broadcast_messages(id) ON DELETE CASCADE,
            group_id BIGINT REFERENCES groups(chat_id) ON DELETE SET NULL,
            hub_message_id BIGINT NOT NULL,
            views INTEGER NOT NULL DEFAULT 0,
            zwsp_toggle BOOLEAN NOT NULL DEFAULT false,
            last_synced TIMESTAMP WITH TIME ZONE,
            CONSTRAINT uq_hub_broadcast_group UNIQUE (broadcast_id, group_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_analytics_sources_broadcast_id ON analytics_sources (broadcast_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_analytics_sources_last_synced ON analytics_sources (last_synced)")


def downgrade() -> None:
    op.drop_table("analytics_sources")
