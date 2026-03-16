"""Add cuisine_preference to users; create exercise_logs table

Revision ID: 004
Revises: 003
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # cuisine_preference on users — nullable, user sets it via /cuisine
    op.add_column('users', sa.Column('cuisine_preference', sa.String(50), nullable=True))

    # exercise_logs — records per-exercise performance for progressive overload
    op.create_table(
        'exercise_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('workout_log_id', sa.Integer(), sa.ForeignKey('workout_logs.id'), nullable=True),
        sa.Column('exercise_name', sa.String(100), nullable=False),
        sa.Column('weight_kg', sa.Float(), nullable=True),
        sa.Column('reps', sa.Integer(), nullable=True),
        sa.Column('sets', sa.Integer(), nullable=True),
        sa.Column('rpe', sa.Float(), nullable=True),
        sa.Column('logged_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_exercise_logs_user_id', 'exercise_logs', ['user_id'])
    op.create_index('ix_exercise_logs_logged_at', 'exercise_logs', ['logged_at'])
    op.create_index('ix_exercise_logs_workout_log_id', 'exercise_logs', ['workout_log_id'])


def downgrade() -> None:
    op.drop_table('exercise_logs')
    op.drop_column('users', 'cuisine_preference')
