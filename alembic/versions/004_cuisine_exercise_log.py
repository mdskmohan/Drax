"""Add cuisine_preference to users; create exercise_logs table

Revision ID: 004
Revises: 003
Create Date: 2026-03-16
"""
from alembic import op

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS cuisine_preference VARCHAR(50)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS exercise_logs (
            id          SERIAL PRIMARY KEY,
            user_id     BIGINT NOT NULL REFERENCES users(id),
            workout_log_id INTEGER REFERENCES workout_logs(id),
            exercise_name VARCHAR(100) NOT NULL,
            weight_kg   FLOAT,
            reps        INTEGER,
            sets        INTEGER,
            rpe         FLOAT,
            logged_at   TIMESTAMPTZ DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_exercise_logs_user_id ON exercise_logs (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_exercise_logs_logged_at ON exercise_logs (logged_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_exercise_logs_workout_log_id ON exercise_logs (workout_log_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS exercise_logs")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS cuisine_preference")
