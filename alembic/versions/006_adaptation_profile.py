"""Add adaptation_profile to users

Revision ID: 006
Revises: 005
Create Date: 2026-03-21
"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('adaptation_profile', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'adaptation_profile')
