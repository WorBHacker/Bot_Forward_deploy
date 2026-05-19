"""add status and username to groups

Revision ID: 0001
Revises:
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = "0000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "groups",
        sa.Column("username", sa.String(255), nullable=True),
    )
    op.add_column(
        "groups",
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="member",
        ),
    )
    # Existing rows that were is_active=True were admins, so back-fill status
    op.execute(
        "UPDATE groups SET status = 'administrator' WHERE is_active = TRUE"
    )


def downgrade() -> None:
    op.drop_column("groups", "status")
    op.drop_column("groups", "username")
