"""Add new features: macros, gym schedule, equipment, health sync, language

Revision ID: 002
Revises: (none — base tables are created by SQLAlchemy init_db on first run)
Create Date: 2026-03-16

NOTE: This is the first Alembic migration. Core tables (users, meal_logs, etc.)
are created by `init_db()` via SQLAlchemy metadata.create_all() on startup.
This migration only adds new columns to the existing users table and extends
the onboarding_state enum.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers
revision = '002'
down_revision = None  # set to your previous migration ID if one exists
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to users table
    op.add_column('users', sa.Column('gym_schedule', JSON, nullable=True, server_default='[]'))
    op.add_column('users', sa.Column('language', sa.String(10), nullable=True, server_default='en'))
    op.add_column('users', sa.Column('protein_target_g', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('carbs_target_g', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('fat_target_g', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('equipment_list', JSON, nullable=True, server_default='[]'))
    op.add_column('users', sa.Column('equipment_setup', sa.String(20), nullable=True, server_default='gym'))
    op.add_column('users', sa.Column('health_sync_token', sa.String(64), nullable=True))

    # Add new enum values to onboarding_state
    # Note: PostgreSQL requires ALTER TYPE for enum additions
    op.execute("ALTER TYPE onboardingstate ADD VALUE IF NOT EXISTS 'collecting_gym_schedule'")
    op.execute("ALTER TYPE onboardingstate ADD VALUE IF NOT EXISTS 'collecting_equipment'")
    op.execute("ALTER TYPE onboardingstate ADD VALUE IF NOT EXISTS 'collecting_language'")

    # Unique index on health_sync_token
    op.create_index('ix_users_health_sync_token', 'users', ['health_sync_token'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_health_sync_token', table_name='users')
    op.drop_column('users', 'health_sync_token')
    op.drop_column('users', 'equipment_setup')
    op.drop_column('users', 'equipment_list')
    op.drop_column('users', 'fat_target_g')
    op.drop_column('users', 'carbs_target_g')
    op.drop_column('users', 'protein_target_g')
    op.drop_column('users', 'language')
    op.drop_column('users', 'gym_schedule')
