"""Phase 5A welfare records — WorkoutRecord, CheckInRecord, TestBarnRecord.

Revision ID: 002
Revises: 001
Create Date: 2026-04-03
"""

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "workout_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("horse_epc", sa.String(), sa.ForeignKey("horses.epc"), nullable=False),
        sa.Column("workout_date", sa.String(10), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=False),
        sa.Column("surface", sa.String(32), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("track_condition", sa.String(32), nullable=True),
        sa.Column("trainer_name", sa.String(128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workout_records_horse", "workout_records", ["horse_epc"])

    op.create_table(
        "checkin_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("horse_epc", sa.String(), sa.ForeignKey("horses.epc"), nullable=False),
        sa.Column("race_id", sa.Integer(), sa.ForeignKey("races.id"), nullable=True),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scanned_by", sa.String(128), nullable=True),
        sa.Column("location", sa.String(128), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_checkin_records_horse", "checkin_records", ["horse_epc"])
    op.create_index("ix_checkin_records_race", "checkin_records", ["race_id"])

    op.create_table(
        "test_barn_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("horse_epc", sa.String(), sa.ForeignKey("horses.epc"), nullable=False),
        sa.Column("race_id", sa.Integer(), sa.ForeignKey("races.id"), nullable=True),
        sa.Column("checkin_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checkin_by", sa.String(128), nullable=True),
        sa.Column("checkout_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checkout_by", sa.String(128), nullable=True),
        sa.Column("sample_id", sa.String(64), nullable=True),
        sa.Column("result", sa.String(32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_test_barn_horse", "test_barn_records", ["horse_epc"])


def downgrade() -> None:
    op.drop_index("ix_test_barn_horse", "test_barn_records")
    op.drop_table("test_barn_records")
    op.drop_index("ix_checkin_records_race", "checkin_records")
    op.drop_index("ix_checkin_records_horse", "checkin_records")
    op.drop_table("checkin_records")
    op.drop_index("ix_workout_records_horse", "workout_records")
    op.drop_table("workout_records")