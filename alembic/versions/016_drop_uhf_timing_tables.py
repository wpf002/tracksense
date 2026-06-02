"""Phase 1 — drop UHF/timing tables (gates, gate reads, track path, breaks).

The pivot to a HISA compliance platform removes the fixed-gate UHF timing
engine, in-race sectional timing, the broadcast TrackMap, and the gate-sim
workout/gate-break features. The tables that backed them are no longer used.

Revision ID: 016
Revises: 015
Create Date: 2026-06-02
"""

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # Drop in FK-safe order (children before parents). IF EXISTS keeps this
    # safe whether the DB was built via migrations or create_all/start.sh.
    for table in ("gate_reads", "break_records", "track_path_points", "gate_records"):
        op.execute(f"DROP TABLE IF EXISTS {table}")


def downgrade() -> None:
    op.create_table(
        "gate_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("venue_id", sa.String, sa.ForeignKey("venue_records.venue_id"), nullable=False),
        sa.Column("reader_id", sa.String, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("distance_m", sa.Float, nullable=False),
        sa.Column("is_finish", sa.Boolean, server_default=sa.false()),
        sa.Column("position_x", sa.Float, nullable=True),
        sa.Column("position_y", sa.Float, nullable=True),
        sa.UniqueConstraint("venue_id", "reader_id"),
    )
    op.create_table(
        "gate_reads",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("race_id", sa.Integer, sa.ForeignKey("races.id"), nullable=False),
        sa.Column("horse_epc", sa.String, sa.ForeignKey("horses.epc"), nullable=False),
        sa.Column("reader_id", sa.String, nullable=False),
        sa.Column("gate_name", sa.String, nullable=False),
        sa.Column("distance_m", sa.Float, nullable=False),
        sa.Column("race_elapsed_ms", sa.Integer, nullable=False),
        sa.Column("wall_time", sa.Float, nullable=True),
        sa.UniqueConstraint("race_id", "horse_epc", "reader_id"),
    )
    op.create_table(
        "track_path_points",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("venue_id", sa.String, sa.ForeignKey("venue_records.venue_id"), nullable=False, index=True),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("x", sa.Float, nullable=False),
        sa.Column("y", sa.Float, nullable=False),
        sa.UniqueConstraint("venue_id", "sequence"),
    )
    op.create_table(
        "break_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("horse_epc", sa.String, sa.ForeignKey("horses.epc"), nullable=False, index=True),
        sa.Column("race_id", sa.Integer, sa.ForeignKey("races.id"), nullable=True, index=True),
        sa.Column("reaction_ms", sa.Integer, nullable=False),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("baseline_delta_ms", sa.Integer, nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="race"),
    )
