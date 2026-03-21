"""Add adaptation_profile to users

Revision ID: 006
Revises: 005
Create Date: 2026-03-21
"""
from alembic import op

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS adaptation_profile JSON")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS adaptation_profile")
