"""Add cuisine_last_changed_at to users

Revision ID: 005
Revises: 004
Create Date: 2026-03-16
"""
from alembic import op

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS cuisine_last_changed_at TIMESTAMPTZ")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS cuisine_last_changed_at")
