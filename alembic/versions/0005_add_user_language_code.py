"""add language_code to users

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-08
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS language_code VARCHAR(8) NOT NULL DEFAULT 'ru'")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS language_code")
