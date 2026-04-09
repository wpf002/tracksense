"""Add biosensor_readings table for race-day wearable telemetry.

Revision ID: 014
Revises: 013
Create Date: 2026-04-09
"""

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "biosensor_readings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("horse_epc", sa.String, sa.ForeignKey("horses.epc"), nullable=False, index=True),
        sa.Column("race_id", sa.Integer, sa.ForeignKey("races.id"), nullable=True, index=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heart_rate_bpm", sa.Integer, nullable=True),
        sa.Column("temperature_c", sa.Float, nullable=True),
        sa.Column("stride_hz", sa.Float, nullable=True),
        sa.Column("source", sa.String(64), nullable=False, server_default="wearable"),
    )


def downgrade() -> None:
    op.drop_table("biosensor_readings")
