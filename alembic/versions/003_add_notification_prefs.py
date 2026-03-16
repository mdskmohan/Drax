"""Add per-user notification preferences and last-sent tracking

Revision ID: 003
Revises: 002
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("notification_prefs", JSON, nullable=True))
    op.add_column("users", sa.Column("notifications_last_sent", JSON, nullable=True))


def downgrade():
    op.drop_column("users", "notifications_last_sent")
    op.drop_column("users", "notification_prefs")
