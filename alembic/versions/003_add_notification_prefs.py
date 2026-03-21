"""Add per-user notification preferences and last-sent tracking

Revision ID: 003
Revises: 002
Create Date: 2026-03-16
"""
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS notification_prefs JSON")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS notifications_last_sent JSON")


def downgrade():
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS notifications_last_sent")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS notification_prefs")
