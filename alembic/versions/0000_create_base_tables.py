"""create base tables

Revision ID: 0000
Revises:
Create Date: 2026-05-13
"""
from alembic import op

revision = "0000"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enum types
    op.execute("CREATE TYPE userrole AS ENUM ('owner', 'superadmin', 'admin', 'guest')")
    op.execute("CREATE TYPE messagestatus AS ENUM ('pending', 'approved', 'rejected', 'sent', 'failed')")

    # groups (without username, status — added by 0001)
    op.execute("""
        CREATE TABLE groups (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT UNIQUE NOT NULL,
            title VARCHAR(255) NOT NULL DEFAULT 'Unknown',
            is_active BOOLEAN NOT NULL DEFAULT FALSE,
            added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            removed_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX ix_groups_chat_id ON groups (chat_id)")

    # users (without language_code — added by 0005)
    op.execute("""
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE NOT NULL,
            username VARCHAR(255),
            full_name VARCHAR(255),
            role userrole NOT NULL,
            added_by BIGINT,
            added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
    """)
    op.execute("CREATE INDEX ix_users_user_id ON users (user_id)")

    # broadcast_messages (without channel_views, views_synced_at, content_full, zwsp_toggle — added by 0002)
    op.execute("""
        CREATE TABLE broadcast_messages (
            id SERIAL PRIMARY KEY,
            master_message_id BIGINT NOT NULL,
            master_chat_id BIGINT NOT NULL,
            media_group_ids TEXT,
            content_preview TEXT,
            status messagestatus NOT NULL DEFAULT 'pending',
            censorship_triggered BOOLEAN NOT NULL DEFAULT FALSE,
            censorship_reason TEXT,
            approved_by BIGINT,
            approved_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            control_panel_message_id BIGINT
        )
    """)

    # message_stats (without member_count, zwsp_toggle — added by 0003)
    op.execute("""
        CREATE TABLE message_stats (
            id SERIAL PRIMARY KEY,
            broadcast_id INTEGER NOT NULL REFERENCES broadcast_messages(id) ON DELETE CASCADE,
            group_id BIGINT REFERENCES groups(chat_id) ON DELETE SET NULL,
            telegram_message_id BIGINT,
            views INTEGER NOT NULL DEFAULT 0,
            last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_broadcast_group UNIQUE (broadcast_id, group_id)
        )
    """)

    # admin_actions
    op.execute("""
        CREATE TABLE admin_actions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            action_type VARCHAR(50) NOT NULL,
            target_id BIGINT,
            details TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ix_admin_actions_user_id ON admin_actions (user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS admin_actions")
    op.execute("DROP TABLE IF EXISTS message_stats")
    op.execute("DROP TABLE IF EXISTS broadcast_messages")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TABLE IF EXISTS groups")
    op.execute("DROP TYPE IF EXISTS messagestatus")
    op.execute("DROP TYPE IF EXISTS userrole")
