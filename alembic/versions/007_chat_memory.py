"""add chat_memory column to users

Revision ID: 007
Revises: 006
Create Date: 2026-03-21
"""
from alembic import op

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS chat_memory JSON")


def downgrade():
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS chat_memory")
