"""Initial schema — all Phase 3 tables.

Revision ID: 001
Revises: —
Create Date: 2026-04-02
"""

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "horses",
        sa.Column("epc", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("breed", sa.String(), nullable=True),
        sa.Column("date_of_birth", sa.String(), nullable=True),
        sa.Column("implant_date", sa.String(), nullable=True),
        sa.Column("implant_vet", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "owners",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("horse_epc", sa.String(), sa.ForeignKey("horses.epc"), nullable=False),
        sa.Column("owner_name", sa.String(), nullable=False),
        sa.Column("from_date", sa.String(), nullable=True),
        sa.Column("to_date", sa.String(), nullable=True),
    )

    op.create_table(
        "trainers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("horse_epc", sa.String(), sa.ForeignKey("horses.epc"), nullable=False),
        sa.Column("trainer_name", sa.String(), nullable=False),
        sa.Column("from_date", sa.String(), nullable=True),
        sa.Column("to_date", sa.String(), nullable=True),
    )

    op.create_table(
        "venue_records",
        sa.Column("venue_id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("total_distance_m", sa.Float(), nullable=False),
    )

    op.create_table(
        "gate_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("venue_id", sa.String(), sa.ForeignKey("venue_records.venue_id"), nullable=False),
        sa.Column("reader_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=False),
        sa.Column("is_finish", sa.Boolean(), default=False),
        sa.UniqueConstraint("venue_id", "reader_id"),
    )

    op.create_table(
        "races",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("venue_id", sa.String(), sa.ForeignKey("venue_records.venue_id"), nullable=False),
        sa.Column("race_date", sa.DateTime(), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=False),
        sa.Column("surface", sa.String(), default="turf"),
        sa.Column("conditions", sa.String(), nullable=True),
        sa.Column("status", sa.String(), default="pending"),
    )

    op.create_table(
        "race_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("race_id", sa.Integer(), sa.ForeignKey("races.id"), nullable=False),
        sa.Column("horse_epc", sa.String(), sa.ForeignKey("horses.epc"), nullable=False),
        sa.Column("saddle_cloth", sa.String(), nullable=False),
        sa.UniqueConstraint("race_id", "horse_epc"),
        sa.UniqueConstraint("race_id", "saddle_cloth"),
    )

    op.create_table(
        "gate_reads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("race_id", sa.Integer(), sa.ForeignKey("races.id"), nullable=False),
        sa.Column("horse_epc", sa.String(), sa.ForeignKey("horses.epc"), nullable=False),
        sa.Column("reader_id", sa.String(), nullable=False),
        sa.Column("gate_name", sa.String(), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=False),
        sa.Column("race_elapsed_ms", sa.Integer(), nullable=False),
        sa.Column("wall_time", sa.Float(), nullable=True),
        sa.UniqueConstraint("race_id", "horse_epc", "reader_id"),
    )

    op.create_table(
        "race_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("race_id", sa.Integer(), sa.ForeignKey("races.id"), nullable=False),
        sa.Column("horse_epc", sa.String(), sa.ForeignKey("horses.epc"), nullable=False),
        sa.Column("finish_position", sa.Integer(), nullable=False),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False),
        sa.UniqueConstraint("race_id", "horse_epc"),
        sa.UniqueConstraint("race_id", "finish_position"),
    )

    op.create_table(
        "vet_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("horse_epc", sa.String(), sa.ForeignKey("horses.epc"), nullable=False),
        sa.Column("event_date", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("vet_name", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("vet_records")
    op.drop_table("race_results")
    op.drop_table("gate_reads")
    op.drop_table("race_entries")
    op.drop_table("races")
    op.drop_table("gate_records")
    op.drop_table("venue_records")
    op.drop_table("trainers")
    op.drop_table("owners")
    op.drop_table("horses")