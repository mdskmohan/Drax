"""Add new features: macros, gym schedule, equipment, health sync, language

Revision ID: 002
Revises: (none — base tables are created by SQLAlchemy init_db on first run)
Create Date: 2026-03-16

All ADD COLUMN statements use IF NOT EXISTS so this migration is safe to run
on a DB that was already bootstrapped via SQLAlchemy create_all.
"""
from alembic import op

revision = '002'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS gym_schedule JSON DEFAULT '[]'")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'en'")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS protein_target_g INTEGER")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS carbs_target_g INTEGER")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS fat_target_g INTEGER")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS equipment_list JSON DEFAULT '[]'")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS equipment_setup VARCHAR(20) DEFAULT 'gym'")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS health_sync_token VARCHAR(64)")

    op.execute("ALTER TYPE onboardingstate ADD VALUE IF NOT EXISTS 'collecting_gym_schedule'")
    op.execute("ALTER TYPE onboardingstate ADD VALUE IF NOT EXISTS 'collecting_equipment'")
    op.execute("ALTER TYPE onboardingstate ADD VALUE IF NOT EXISTS 'collecting_language'")

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_users_health_sync_token
        ON users (health_sync_token)
        WHERE health_sync_token IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_health_sync_token")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS health_sync_token")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS equipment_setup")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS equipment_list")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS fat_target_g")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS carbs_target_g")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS protein_target_g")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS language")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS gym_schedule")
